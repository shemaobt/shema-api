"""ENG-1392 — two tablets on one passage share one session and never halt on a collision.

In her app a second tablet opening the same passage and language joins the same session, and
when two turns collide the later one moves after the other reply, or is refused quietly when
the server cannot tell. Ours took no claim for a team turn: two turns each read the session
and ran the Guide, and the later one to land was refused as a stale version, so that tablet
called a person for a turn it had every right to send.

Racing requests run on independent ``AsyncSession``s, so the **Turn claim** is proven on the
database and not on one identity map. A request on "another instance" lands on a process
whose in-flight registry never saw the first, which is what two Cloud Run instances are.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import sessions as sessions_api
from app.core.config import get_settings
from app.db.models.internalization_room import IRSession, IRTurn
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.sessions import append_opening, create_session
from app.services.internalization_room.turn_dedup import remember_turn
from app.services.internalization_room.voice_handles import clip_url
from tests.device_harness import TABLET_TEAM
from tests.opening_harness import (
    NOTE_PT_P03,
    a_scripted_room,
    another_tablet_of,
    ask_for_the_opening,
    the_tablet_opens,
    the_team_says,
)
from tests.release_harness import P02, P, a_claimed_device
from tests.room_harness import room_client, the_bucket_is_in_memory, the_room_speaks
from tests.scene_rehearsal_harness import IR, a_room, read_by_b, recorded, translated
from tests.scene_rehearsal_harness import SAID as FRASE_SAID
from tests.tablet_turn_harness import the_room_opens
from tests.turn_claim_harness import (
    OPENING,
    SAID,
    Guide,
    Voice,
    a_voice,
    another_instance,
    claim_on_the_row,
    clip_of,
    conversation,
    dead_after,
    speak,
    the_guide_is,
)

REPLY_A = "Vamos ficar nesta cena. O que voces contariam?"
REPLY_B = "E depois, o que Rute respondeu a Noemi?"
SAID_BY_A = "Noemi voltou para Belem com Rute, e as duas choraram no caminho"
SAID_BY_B = "Rute ficou"


@pytest.fixture()
def voice(monkeypatch: pytest.MonkeyPatch) -> Voice:
    return a_voice(monkeypatch)


def _the_wait_is(monkeypatch: pytest.MonkeyPatch, ms: int) -> None:
    monkeypatch.setattr(get_settings(), "internalization_room_opening_wait_ms", ms)


async def _an_opened_session(db: AsyncSession, pericope: str = P) -> str:
    """A session whose opening was already said, without asking the Guide for it."""
    session = await create_session(db, project_id=TABLET_TEAM, pericope=pericope, language="pt")
    await append_opening(db, session, guide_response=OPENING)
    return str(session.id)


OPENED = [("team", NOTE_PT_P03), ("guide", OPENING)]


async def _turns_stored_under(rival_factory, session_id: str, turn_id: str) -> int:
    async with rival_factory() as fresh:
        return int(
            await fresh.scalar(
                select(func.count())
                .select_from(IRTurn)
                .where(IRTurn.session_id == session_id, IRTurn.turn_id == turn_id)
            )
        )


async def _until(holds: Callable[[], bool]) -> None:
    async def _looking() -> None:
        while not holds():
            await asyncio.sleep(0.05)

    await asyncio.wait_for(_looking(), timeout=5)


# One session


@pytest.fixture()
async def opening_client(db_session: AsyncSession, rival_factory, monkeypatch: pytest.MonkeyPatch):
    the_bucket_is_in_memory(monkeypatch)
    the_room_speaks(monkeypatch)
    async with room_client(db_session, monkeypatch, per_request=rival_factory) as client:
        yield client


async def test_the_same_passage_in_english_is_another_session(
    opening_client, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    a_scripted_room(monkeypatch)
    team, tablet_a = await a_claimed_device(db_session)
    tablet_b = await another_tablet_of(db_session, team)

    portuguese = await the_tablet_opens(
        opening_client, tablet_a, {"pericope": P02, "language": "pt"}
    )
    english = await the_tablet_opens(opening_client, tablet_b, {"pericope": P02, "language": "en"})

    assert english["session_id"] != portuguese["session_id"]


async def test_a_create_that_lands_late_returns_the_one_session(
    opening_client, db_session: AsyncSession, rival_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = a_scripted_room(monkeypatch)
    team, tablet = await a_claimed_device(db_session)
    key = {"pericope": P02, "language": "pt"}
    opened = await the_tablet_opens(opening_client, tablet, key)
    await the_room_opens(opening_client, tablet, opened["session_id"])
    await the_team_says(opening_client, script, tablet, opened["session_id"], SAID)

    resent = await the_tablet_opens(opening_client, tablet, key)

    assert resent["session_id"] == opened["session_id"]
    said = [text for role, text in await conversation(rival_factory, resent["session_id"])]
    assert SAID in said
    async with rival_factory() as fresh:
        rows = await fresh.scalar(
            select(func.count())
            .select_from(IRSession)
            .where(
                IRSession.project_id == team.id,
                IRSession.pericope == P02,
                IRSession.language == "pt",
            )
        )
    assert rows == 1, "o reenvio da criacao deixou uma segunda sessao para a mesma passagem"


# The turn claim


async def test_two_turns_at_nearly_the_same_moment_the_later_is_placed_after_the_other_reply_and_voiced(  # noqa: E501
    db_session: AsyncSession, rival_factory, voice: Voice, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_id = await _an_opened_session(db_session)
    guide = the_guide_is(monkeypatch, Guide(lines=(REPLY_A, REPLY_B)))

    async with (
        rival_factory() as one,
        rival_factory() as two,
        room_client(one, monkeypatch) as tablet_a,
        room_client(two, monkeypatch) as tablet_b,
    ):
        a = asyncio.create_task(speak(tablet_a, session_id, "a"))
        await asyncio.wait_for(guide.thinking.wait(), timeout=5)
        await asyncio.sleep(0.2)
        b = asyncio.create_task(speak(tablet_b, session_id, "b"))
        await asyncio.wait({b}, timeout=0.5)
        assert not b.done(), "o segundo turno foi respondido enquanto o primeiro era redigido"
        guide.answer.set()
        first, second = await asyncio.wait_for(asyncio.gather(a, b), timeout=20)

    assert first.status_code == 200, first.text[:300]
    assert second.status_code == 200, second.text[:300]
    assert await conversation(rival_factory, session_id) == [
        *OPENED,
        ("team", SAID),
        ("guide", REPLY_A),
        ("team", SAID),
        ("guide", REPLY_B),
    ]
    assert REPLY_B in voice.said


async def test_two_turns_sent_one_second_apart_the_seconds_reply_reads_the_firsts(
    db_session: AsyncSession, rival_factory, voice: Voice, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_id = await _an_opened_session(db_session)
    guide = the_guide_is(monkeypatch, Guide(lines=(REPLY_A, REPLY_B)))
    guide.first_takes = 2.0

    async with (
        rival_factory() as one,
        rival_factory() as two,
        room_client(one, monkeypatch) as tablet_a,
        room_client(two, monkeypatch) as tablet_b,
    ):
        a = asyncio.create_task(speak(tablet_a, session_id, "a"))
        await asyncio.sleep(1.0)
        b = asyncio.create_task(speak(tablet_b, session_id, "b"))
        first, second = await asyncio.wait_for(asyncio.gather(a, b), timeout=20)

    assert first.status_code == 200, first.text[:300]
    assert second.status_code == 200, second.text[:300]
    assert len(guide.given) == 2
    assert REPLY_A in guide.given[1], "a segunda resposta foi redigida sem a primeira"


async def test_a_turn_still_waiting_at_the_bound_is_refused_as_a_collision_not_voiced_and_not_stored(  # noqa: E501
    db_session: AsyncSession, rival_factory, voice: Voice, monkeypatch: pytest.MonkeyPatch
) -> None:
    _the_wait_is(monkeypatch, 300)
    session_id = await _an_opened_session(db_session)
    guide = the_guide_is(monkeypatch, Guide(lines=(REPLY_A, REPLY_B)))

    async with (
        rival_factory() as one,
        rival_factory() as two,
        room_client(one, monkeypatch) as tablet_a,
        room_client(two, monkeypatch) as tablet_b,
    ):
        a = asyncio.create_task(speak(tablet_a, session_id, "a"))
        await asyncio.wait_for(guide.thinking.wait(), timeout=5)
        try:
            refused = await asyncio.wait_for(speak(tablet_b, session_id, "b"), timeout=3)
        finally:
            guide.answer.set()
        first = await asyncio.wait_for(a, timeout=10)

    assert refused.status_code == 409, refused.text[:300]
    assert refused.json()["code"] == "TURN_COLLISION"
    assert first.status_code == 200, first.text[:300]
    assert await conversation(rival_factory, session_id) == [
        *OPENED,
        ("team", SAID),
        ("guide", REPLY_A),
    ]
    assert guide.asked == 1
    assert await _turns_stored_under(rival_factory, session_id, "b") == 0
    assert voice.said == [REPLY_A]


async def test_the_bound_is_counted_from_the_claim_not_from_the_waiters_arrival(
    db_session: AsyncSession, rival_factory, voice: Voice, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The claim is taken 1.5 s before B arrives on a 2 s wait: counted from the claim B has
    0.5 s left, counted from its arrival it would wait 2 s; 1.5 s lies a second from either."""
    _the_wait_is(monkeypatch, 2000)
    session_id = await _an_opened_session(db_session)
    guide = the_guide_is(monkeypatch, Guide(lines=(REPLY_A, REPLY_B)))
    loop = asyncio.get_running_loop()

    async with (
        rival_factory() as one,
        rival_factory() as two,
        room_client(one, monkeypatch) as tablet_a,
        room_client(two, monkeypatch) as tablet_b,
    ):
        a = asyncio.create_task(speak(tablet_a, session_id, "a"))
        await asyncio.wait_for(guide.thinking.wait(), timeout=5)
        await asyncio.sleep(1.5)
        sent_at = loop.time()
        try:
            refused = await asyncio.wait_for(speak(tablet_b, session_id, "b"), timeout=5)
            waited = loop.time() - sent_at
        finally:
            guide.answer.set()
        await asyncio.wait_for(a, timeout=10)

    assert refused.status_code == 409, refused.text[:300]
    assert waited < 1.5, f"a espera foi contada da chegada do turno: {waited:.2f} s"


async def test_when_the_waited_on_turn_fails_the_waiter_runs_on_the_conversation_as_it_stands(
    db_session: AsyncSession, rival_factory, voice: Voice, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_id = await _an_opened_session(db_session)
    guide = the_guide_is(monkeypatch, Guide(lines=(REPLY_A, REPLY_B)))
    guide.first_fails = True

    async with (
        rival_factory() as one,
        rival_factory() as two,
        room_client(one, monkeypatch) as tablet_a,
        room_client(two, monkeypatch) as tablet_b,
    ):
        a = asyncio.create_task(speak(tablet_a, session_id, "a"))
        await asyncio.wait_for(guide.thinking.wait(), timeout=5)
        b = asyncio.create_task(speak(tablet_b, session_id, "b"))
        await asyncio.wait({b}, timeout=0.5)
        assert not b.done(), "o turno de B nao esperou pelo de A"
        guide.answer.set()
        failed, ran = await asyncio.wait_for(asyncio.gather(a, b), timeout=20)

    assert failed.status_code == 502, failed.text[:300]
    assert ran.status_code == 200, ran.text[:300]
    assert await conversation(rival_factory, session_id) == [
        *OPENED,
        ("team", SAID),
        ("guide", REPLY_B),
    ]
    assert guide.asked == 2


async def test_asking_for_the_last_line_again_claims_nothing_and_never_waits(
    db_session: AsyncSession, rival_factory, voice: Voice, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_id = await _an_opened_session(db_session)
    guide = the_guide_is(monkeypatch, Guide())
    await claim_on_the_row(rival_factory, session_id, "outro-tablet", datetime.now(UTC))

    async with rival_factory() as one, room_client(one, monkeypatch) as tablet:
        again = await asyncio.wait_for(ask_for_the_opening(tablet, session_id, "volta"), timeout=1)

    assert again.status_code == 200, again.text[:300]
    assert again.json()["audio_url"] == clip_url(clip_of(OPENING), session_id=session_id)
    assert guide.asked == 0


async def test_a_claim_an_older_instance_left_with_its_answer_stored_is_no_claim_and_a_team_turn_runs_at_once(  # noqa: E501
    db_session: AsyncSession, rival_factory, voice: Voice, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The instance before this one answered the opening under its claim and never cleared it,
    which is what the deploy leaves on every session opened in the minutes before it."""
    session_id = await _an_opened_session(db_session)
    guide = the_guide_is(monkeypatch, Guide(lines=(REPLY_A,)))
    guide.answer.set()
    await claim_on_the_row(rival_factory, session_id, "instancia-velha", datetime.now(UTC))
    async with rival_factory() as old_instance:
        await remember_turn(
            old_instance, session_id=session_id, turn_id="instancia-velha", response={}
        )
        await old_instance.commit()

    async with rival_factory() as one, room_client(one, monkeypatch) as tablet:
        spoken = await asyncio.wait_for(speak(tablet, session_id, "fala"), timeout=3)

    assert spoken.status_code == 200, spoken.text[:300]
    assert await conversation(rival_factory, session_id) == [
        *OPENED,
        ("team", SAID),
        ("guide", REPLY_A),
    ]


async def test_a_turn_sent_first_is_answered_first_however_long_its_hearing_takes(
    db_session: AsyncSession, rival_factory, voice: Voice, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A's long recording takes 3 s to hear and B's short one none, B sent 1 s after A."""
    session_id = await _an_opened_session(db_session)
    guide = the_guide_is(monkeypatch, Guide(lines=(REPLY_A, REPLY_B)))
    guide.answer.set()
    heard_by: list[str] = []

    async def heard(*_: Any, **__: Any) -> HeardSpeech:
        heard_by.append("a" if not heard_by else "b")
        if len(heard_by) == 1:
            await asyncio.sleep(3.0)
            return HeardSpeech(text=SAID_BY_A)
        return HeardSpeech(text=SAID_BY_B)

    monkeypatch.setattr(sessions_api, "heard_speech", heard)

    async with (
        rival_factory() as one,
        rival_factory() as two,
        room_client(one, monkeypatch) as tablet_a,
        room_client(two, monkeypatch) as tablet_b,
    ):
        a = asyncio.create_task(speak(tablet_a, session_id, "a"))
        await asyncio.sleep(1.0)
        b = asyncio.create_task(speak(tablet_b, session_id, "b"))
        first, second = await asyncio.wait_for(asyncio.gather(a, b), timeout=20)

    assert first.status_code == 200, first.text[:300]
    assert second.status_code == 200, second.text[:300]
    assert await conversation(rival_factory, session_id) == [
        *OPENED,
        ("team", SAID_BY_A),
        ("guide", REPLY_A),
        ("team", SAID_BY_B),
        ("guide", REPLY_B),
    ]


async def test_a_team_turn_that_ran_past_a_slow_opening_is_the_one_the_next_turn_waits_on(
    db_session: AsyncSession, rival_factory, voice: Voice, monkeypatch: pytest.MonkeyPatch
) -> None:
    _the_wait_is(monkeypatch, 300)
    session = await create_session(db_session, project_id=TABLET_TEAM, pericope=P, language="pt")
    guide = the_guide_is(monkeypatch, Guide(lines=(OPENING, REPLY_A, REPLY_B)))

    async with (
        rival_factory() as one,
        rival_factory() as two,
        room_client(one, monkeypatch) as opening_tablet,
        room_client(two, monkeypatch) as speaking_tablet,
    ):
        opening = asyncio.create_task(ask_for_the_opening(opening_tablet, session.id, "abre"))
        await asyncio.wait_for(guide.thinking.wait(), timeout=5)
        try:
            ran_past = await asyncio.wait_for(speak(speaking_tablet, session.id, "t"), timeout=5)
            next_turn = await asyncio.wait_for(speak(speaking_tablet, session.id, "u"), timeout=5)
        finally:
            guide.answer.set()
        await asyncio.wait_for(opening, timeout=10)

    assert ran_past.status_code == 200, ran_past.text[:300]
    assert next_turn.status_code == 200, next_turn.text[:300]
    assert await conversation(rival_factory, session.id) == [
        ("team", SAID),
        ("guide", REPLY_A),
        ("team", SAID),
        ("guide", REPLY_B),
    ]


async def test_a_claim_naming_a_turn_but_no_time_never_holds_a_turn_up(
    db_session: AsyncSession, rival_factory, voice: Voice, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A hand-edited row; the room itself never writes one."""
    session_id = await _an_opened_session(db_session)
    guide = the_guide_is(monkeypatch, Guide(lines=(REPLY_A,)))
    guide.answer.set()
    await claim_on_the_row(rival_factory, session_id, "sem-hora", None)

    async with rival_factory() as one, room_client(one, monkeypatch) as tablet:
        spoken = await asyncio.wait_for(speak(tablet, session_id, "fala"), timeout=5)

    assert spoken.status_code == 200, spoken.text[:300]
    assert await conversation(rival_factory, session_id) == [
        *OPENED,
        ("team", SAID),
        ("guide", REPLY_A),
    ]


# The scene door


@pytest.fixture()
async def scene_room(db_session: AsyncSession, rival_factory, monkeypatch: pytest.MonkeyPatch):
    async with a_room(db_session, rival_factory, monkeypatch) as room:
        yield room


async def _a_translated_rehearsal(scene_room, session_id: str) -> str:
    rehearsal_id = await recorded(scene_room, session_id)
    await translated(scene_room, session_id, rehearsal_id, [(0, 4000)])
    return rehearsal_id


async def _terminei(scene_room, session_id: str, rehearsal_id: str, turn_id: str):
    return await scene_room.client.post(
        f"{IR}/sessions/{session_id}/scene-rehearsals/{rehearsal_id}/send",
        data={"turn_id": turn_id},
    )


async def test_a_terminei_sent_while_a_team_turn_is_answered_waits_and_lands_after_its_reply(
    scene_room, db_session: AsyncSession, rival_factory, voice: Voice, monkeypatch
) -> None:
    session_id = await _an_opened_session(db_session, pericope="P01")
    rehearsal_id = await _a_translated_rehearsal(scene_room, session_id)
    guide = the_guide_is(monkeypatch, Guide(lines=(REPLY_A, REPLY_B)))

    team = asyncio.create_task(speak(scene_room.client, session_id, "fala"))
    await asyncio.wait_for(guide.thinking.wait(), timeout=5)
    sending = asyncio.create_task(_terminei(scene_room, session_id, rehearsal_id, "cena"))
    await asyncio.wait({sending}, timeout=0.5)
    assert not sending.done(), "o «terminei» foi respondido enquanto o turno da equipe era redigido"
    guide.answer.set()
    spoken, sent = await asyncio.wait_for(asyncio.gather(team, sending), timeout=20)

    assert spoken.status_code == 200, spoken.text[:300]
    assert sent.status_code == 200, sent.text[:300]
    after_the_opening = (await conversation(rival_factory, session_id))[len(OPENED) :]
    assert after_the_opening[:2] == [("team", SAID), ("guide", REPLY_A)]
    assert after_the_opening[-2:] == [("team", FRASE_SAID), ("guide", REPLY_B)]


async def test_a_terminei_still_waiting_at_the_bound_is_refused_as_a_collision_stays_unsent_and_can_be_sent_again(  # noqa: E501
    scene_room, db_session: AsyncSession, rival_factory, voice: Voice, monkeypatch
) -> None:
    _the_wait_is(monkeypatch, 300)
    session_id = await _an_opened_session(db_session, pericope="P01")
    rehearsal_id = await _a_translated_rehearsal(scene_room, session_id)
    guide = the_guide_is(monkeypatch, Guide(lines=(REPLY_A, REPLY_B)))

    team = asyncio.create_task(speak(scene_room.client, session_id, "fala"))
    await asyncio.wait_for(guide.thinking.wait(), timeout=5)
    try:
        refused = await asyncio.wait_for(
            _terminei(scene_room, session_id, rehearsal_id, "cena-1"), timeout=3
        )
        listed = await read_by_b(scene_room, session_id)
    finally:
        guide.answer.set()
    spoken = await asyncio.wait_for(team, timeout=10)
    again = await asyncio.wait_for(
        _terminei(scene_room, session_id, rehearsal_id, "cena-2"), timeout=10
    )

    assert refused.status_code == 409, refused.text[:300]
    assert refused.json()["code"] == "TURN_COLLISION"
    (rehearsal,) = [r for r in listed if r["rehearsal_id"] == rehearsal_id]
    assert rehearsal["sent_at"] is None, "o «terminei» recusado ficou marcado como enviado"
    assert spoken.status_code == 200, spoken.text[:300]
    assert again.status_code == 200, again.text[:300]
    after_the_opening = (await conversation(rival_factory, session_id))[len(OPENED) :]
    assert after_the_opening[:2] == [("team", SAID), ("guide", REPLY_A)]
    assert after_the_opening[-2:] == [("team", FRASE_SAID), ("guide", REPLY_B)]


# The folds


async def test_a_claim_that_goes_dead_while_a_request_waits_on_it_is_taken_over(
    db_session: AsyncSession, rival_factory, voice: Voice, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = await create_session(db_session, project_id=TABLET_TEAM, pericope=P, language="pt")
    guide = the_guide_is(monkeypatch, Guide())
    guide.answer.set()
    dies_soon = datetime.now(UTC) - dead_after() + timedelta(seconds=1.5)
    await claim_on_the_row(rival_factory, session.id, "morre", dies_soon)

    async with rival_factory() as one, room_client(one, monkeypatch) as tablet:
        answered = await asyncio.wait_for(
            ask_for_the_opening(tablet, session.id, "assume"), timeout=6
        )

    assert answered.status_code == 200, answered.text[:300]
    assert guide.asked == 1
    assert await conversation(rival_factory, session.id) == [
        ("team", NOTE_PT_P03),
        ("guide", OPENING),
    ]


async def test_a_stale_holders_release_never_frees_the_claim_a_resend_took_over(
    db_session: AsyncSession, rival_factory, voice: Voice, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_id = await _an_opened_session(db_session)
    guide = the_guide_is(monkeypatch, Guide(lines=(REPLY_A, REPLY_A, REPLY_B)))
    guide.first_fails = True
    guide.reply_takes = 2.0

    async with (
        rival_factory() as one,
        rival_factory() as two,
        rival_factory() as three,
        room_client(one, monkeypatch) as stale_tablet,
        room_client(two, monkeypatch) as resending_tablet,
        room_client(three, monkeypatch) as other_tablet,
    ):
        stale = asyncio.create_task(speak(stale_tablet, session_id, "t"))
        await asyncio.wait_for(guide.thinking.wait(), timeout=5)
        outlived = datetime.now(UTC) - dead_after() - timedelta(seconds=5)
        await claim_on_the_row(rival_factory, session_id, "t", outlived)
        another_instance(monkeypatch)
        resend = asyncio.create_task(speak(resending_tablet, session_id, "t"))
        await _until(lambda: guide.asked == 2)
        guide.answer.set()
        failed = await asyncio.wait_for(stale, timeout=5)
        other = asyncio.create_task(speak(other_tablet, session_id, "c"))
        await asyncio.wait({other}, timeout=0.5)
        assert not other.done(), "o outro tablet foi respondido enquanto o reenvio era redigido"
        resent, spoken = await asyncio.wait_for(asyncio.gather(resend, other), timeout=20)

    assert failed.status_code == 502, failed.text[:300]
    assert resent.status_code == 200, resent.text[:300]
    assert spoken.status_code == 200, spoken.text[:300]
    assert await conversation(rival_factory, session_id) == [
        *OPENED,
        ("team", SAID),
        ("guide", REPLY_A),
        ("team", SAID),
        ("guide", REPLY_B),
    ]


async def test_a_resend_of_the_same_turn_id_on_another_instance_joins_the_stored_answer(
    db_session: AsyncSession, rival_factory, voice: Voice, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A wait shorter than the first run's drafting: a resend that waited as another tablet's
    turn does would be refused at it, instead of joining."""
    _the_wait_is(monkeypatch, 300)
    session_id = await _an_opened_session(db_session)
    guide = the_guide_is(monkeypatch, Guide(lines=(REPLY_A, REPLY_B)))

    async with (
        rival_factory() as one,
        rival_factory() as two,
        rival_factory() as three,
        room_client(one, monkeypatch) as first_run,
        room_client(two, monkeypatch) as second_run,
        room_client(three, monkeypatch) as third_run,
    ):
        run_1 = asyncio.create_task(speak(first_run, session_id, "t"))
        await asyncio.wait_for(guide.thinking.wait(), timeout=5)
        another_instance(monkeypatch)
        run_2 = asyncio.create_task(speak(second_run, session_id, "t"))
        await asyncio.wait({run_2}, timeout=1)
        assert not run_2.done(), run_2.result().text[:300]
        assert guide.asked == 1
        guide.answer.set()
        one_answer, two_answer = await asyncio.wait_for(asyncio.gather(run_1, run_2), timeout=20)
        three_answer = await asyncio.wait_for(speak(third_run, session_id, "t"), timeout=10)

    assert one_answer.status_code == 200, one_answer.text[:300]
    assert two_answer.status_code == 200, two_answer.text[:300]
    assert two_answer.json() == one_answer.json()
    assert three_answer.json() == one_answer.json()
    assert await conversation(rival_factory, session_id) == [
        *OPENED,
        ("team", SAID),
        ("guide", REPLY_A),
    ]
    assert await _turns_stored_under(rival_factory, session_id, "t") == 1
    assert guide.asked == 1


async def test_a_resend_whose_first_run_lands_while_it_is_still_being_heard_answers_the_stored_reply(  # noqa: E501
    db_session: AsyncSession, rival_factory, voice: Voice, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_id = await _an_opened_session(db_session)
    guide = the_guide_is(monkeypatch, Guide(lines=(REPLY_A, REPLY_B)))
    heard_by: list[str] = []
    second_hearing = asyncio.Event()

    async def heard(*_: Any, **__: Any) -> HeardSpeech:
        heard_by.append("run")
        if len(heard_by) > 1:
            await second_hearing.wait()
        return HeardSpeech(text=SAID)

    monkeypatch.setattr(sessions_api, "heard_speech", heard)

    async with (
        rival_factory() as one,
        rival_factory() as two,
        room_client(one, monkeypatch) as first_run,
        room_client(two, monkeypatch) as second_run,
    ):
        run_1 = asyncio.create_task(speak(first_run, session_id, "t"))
        await asyncio.wait_for(guide.thinking.wait(), timeout=5)
        another_instance(monkeypatch)
        run_2 = asyncio.create_task(speak(second_run, session_id, "t"))
        await _until(lambda: len(heard_by) == 2)
        guide.answer.set()
        one_answer = await asyncio.wait_for(run_1, timeout=10)
        second_hearing.set()
        two_answer = await asyncio.wait_for(run_2, timeout=10)

    assert one_answer.status_code == 200, one_answer.text[:300]
    assert two_answer.status_code == 200, two_answer.text[:300]
    assert two_answer.json() == one_answer.json()
    assert await conversation(rival_factory, session_id) == [
        *OPENED,
        ("team", SAID),
        ("guide", REPLY_A),
    ]
    assert guide.asked == 1
