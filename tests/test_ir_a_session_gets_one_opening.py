"""ENG-1451 — a session gets one opening, and a team turn during its drafting waits for it.

In her app the opening is claimed once on the session (a write-once lease): a second request
for it gets the same one, and a team turn that arrives while it drafts waits for it. Ours
replayed an answer only by `turn_id`, so two tablets carrying different turn ids each drafted
an opening, and a team turn sent while the opening drafted ran on an empty conversation.

Racing requests run on independent ``AsyncSession``s, so the claim is proven on the database
and not on one identity map. Two cases write a claim on the row with no request of this
process behind it: that is a claim taken by another instance, which a registry in this
process would never see.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import sessions as sessions_api
from app.core.config import get_settings
from app.core.exceptions import UpstreamServiceError
from app.db.models.internalization_room import IRSession, IRTurn
from app.models.internalization_room import TurnResponse
from app.services.internalization_room.coverage import coverage_view
from app.services.internalization_room.sessions import (
    append_opening,
    create_session,
    get_session,
)
from app.services.internalization_room.turn_dedup import remember_turn
from app.services.internalization_room.voice_handles import clip_url
from tests.device_harness import TABLET_TEAM
from tests.opening_harness import (
    NOTE_PT_P03,
    a_scripted_room,
    ask_for_the_opening,
    the_tablet_opens,
    the_team_says,
)
from tests.release_harness import P, a_claimed_device
from tests.room_harness import room_client
from tests.tablet_turn_harness import the_room_opens
from tests.turn_claim_harness import (
    OPENING,
    REPLY,
    SAID,
    Guide,
    Voice,
    a_voice,
    claim_on_the_row,
    clip_of,
    conversation,
    dead_after,
    speak,
    the_guide_is,
)


@pytest.fixture()
def voice(monkeypatch: pytest.MonkeyPatch) -> Voice:
    return a_voice(monkeypatch)


async def test_two_no_audio_requests_with_different_turn_ids_on_a_new_session_draft_one_opening_and_answer_alike(  # noqa: E501
    db_session: AsyncSession, rival_factory, voice: Voice, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = await create_session(db_session, project_id=TABLET_TEAM, pericope=P, language="pt")
    guide = the_guide_is(monkeypatch, Guide())

    async with (
        rival_factory() as one,
        rival_factory() as two,
        room_client(one, monkeypatch) as first_tablet,
        room_client(two, monkeypatch) as second_tablet,
    ):
        first = asyncio.create_task(ask_for_the_opening(first_tablet, session.id, "tablet-a"))
        await asyncio.wait_for(guide.thinking.wait(), timeout=5)
        second = asyncio.create_task(ask_for_the_opening(second_tablet, session.id, "tablet-b"))
        await asyncio.wait({second}, timeout=1)
        assert not second.done(), second.result().text[:300]
        guide.answer.set()
        a, b = await asyncio.wait_for(asyncio.gather(first, second), timeout=10)

    assert a.status_code == 200, a.text[:300]
    assert b.status_code == 200, b.text[:300]
    assert guide.asked == 1, "duas aberturas foram redigidas para uma sessao"
    assert voice.said == [OPENING], "a abertura foi sintetizada mais de uma vez"
    assert a.json()["turn_id"] == "tablet-a"
    assert b.json()["turn_id"] == "tablet-b"
    assert {**a.json(), "turn_id": ""} == {**b.json(), "turn_id": ""}, (
        "os dois tablets ouviram aberturas diferentes"
    )
    assert await conversation(rival_factory, session.id) == [
        ("team", NOTE_PT_P03),
        ("guide", OPENING),
    ]


async def test_a_request_for_the_opening_without_a_turn_id_joins_the_opening_another_tablet_is_drafting(  # noqa: E501
    db_session: AsyncSession, rival_factory, voice: Voice, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = await create_session(db_session, project_id=TABLET_TEAM, pericope=P, language="pt")
    guide = the_guide_is(monkeypatch, Guide())

    async with (
        rival_factory() as one,
        rival_factory() as two,
        room_client(one, monkeypatch) as first_tablet,
        room_client(two, monkeypatch) as second_tablet,
    ):
        first = asyncio.create_task(ask_for_the_opening(first_tablet, session.id, "tablet-a"))
        await asyncio.wait_for(guide.thinking.wait(), timeout=5)
        second = asyncio.create_task(ask_for_the_opening(second_tablet, session.id, None))
        await asyncio.wait({second}, timeout=1)
        assert not second.done(), second.result().text[:300]
        guide.answer.set()
        a, b = await asyncio.wait_for(asyncio.gather(first, second), timeout=10)

    assert a.status_code == 200, a.text[:300]
    assert b.status_code == 200, b.text[:300]
    assert guide.asked == 1, "o pedido sem turn_id redigiu uma segunda abertura"
    assert b.json()["audio_url"] == a.json()["audio_url"]


async def test_a_team_turn_sent_while_the_opening_drafts_is_answered_after_the_opening_in_order(
    db_session: AsyncSession, rival_factory, voice: Voice, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = await create_session(db_session, project_id=TABLET_TEAM, pericope=P, language="pt")
    guide = the_guide_is(monkeypatch, Guide())

    async with (
        rival_factory() as one,
        rival_factory() as two,
        room_client(one, monkeypatch) as opening_tablet,
        room_client(two, monkeypatch) as speaking_tablet,
    ):
        opening = asyncio.create_task(ask_for_the_opening(opening_tablet, session.id, "abre"))
        await asyncio.wait_for(guide.thinking.wait(), timeout=5)
        team = asyncio.create_task(speak(speaking_tablet, session.id, "fala"))
        await asyncio.wait({team}, timeout=0.5)
        assert not team.done(), "o turno da equipe foi respondido antes da abertura"
        guide.answer.set()
        opened, spoken = await asyncio.wait_for(asyncio.gather(opening, team), timeout=20)

    assert opened.status_code == 200, opened.text[:300]
    assert spoken.status_code == 200, spoken.text[:300]
    assert await conversation(rival_factory, session.id) == [
        ("team", NOTE_PT_P03),
        ("guide", OPENING),
        ("team", SAID),
        ("guide", REPLY),
    ]


async def test_a_team_turn_waits_for_the_opening_no_longer_than_the_opening_wait(
    db_session: AsyncSession, rival_factory, voice: Voice, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "internalization_room_opening_wait_ms", 300)
    session = await create_session(db_session, project_id=TABLET_TEAM, pericope=P, language="pt")
    guide = the_guide_is(monkeypatch, Guide())

    async with (
        rival_factory() as one,
        rival_factory() as two,
        room_client(one, monkeypatch) as opening_tablet,
        room_client(two, monkeypatch) as speaking_tablet,
    ):
        opening = asyncio.create_task(ask_for_the_opening(opening_tablet, session.id, "abre"))
        await asyncio.wait_for(guide.thinking.wait(), timeout=5)
        try:
            spoken = await asyncio.wait_for(speak(speaking_tablet, session.id, "fala"), timeout=5)
            assert spoken.status_code == 200, spoken.text[:300]
            assert await conversation(rival_factory, session.id) == [
                ("team", SAID),
                ("guide", REPLY),
            ]
        finally:
            guide.answer.set()
        opened = await asyncio.wait_for(opening, timeout=10)

    assert opened.status_code == 200, opened.text[:300]
    assert await conversation(rival_factory, session.id) == [("team", SAID), ("guide", REPLY)], (
        "a abertura atrasada foi gravada atras do turno da equipe"
    )


async def test_a_team_turns_own_bound_starts_after_its_wait_for_the_opening(
    db_session: AsyncSession, rival_factory, voice: Voice, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The wait ends between 2 s and 3 s into a 4 s bound, so a bound counted from the turn's
    arrival leaves it at most 2 s, and a bound counted after the wait leaves it 4 s: a reply
    taking 3 s fits only the second, by a whole second either way."""
    monkeypatch.setattr(get_settings(), "internalization_room_turn_bound_ms", 4000)
    session = await create_session(db_session, project_id=TABLET_TEAM, pericope=P, language="pt")
    guide = the_guide_is(monkeypatch, Guide())
    guide.first_takes = 2.0
    guide.reply_takes = 3.0

    async with (
        rival_factory() as one,
        rival_factory() as two,
        room_client(one, monkeypatch) as opening_tablet,
        room_client(two, monkeypatch) as speaking_tablet,
    ):
        opening = asyncio.create_task(ask_for_the_opening(opening_tablet, session.id, "abre"))
        await asyncio.wait_for(guide.thinking.wait(), timeout=5)
        team = asyncio.create_task(speak(speaking_tablet, session.id, "fala"))
        opened, spoken = await asyncio.wait_for(asyncio.gather(opening, team), timeout=20)

    assert opened.status_code == 200, opened.text[:300]
    assert spoken.status_code == 200, (
        f"o tempo de espera pela abertura foi descontado do limite do turno: {spoken.text[:300]}"
    )


async def test_a_tablet_whose_opening_failed_leaves_the_claim_free_and_the_next_request_drafts_the_opening(  # noqa: E501
    db_session: AsyncSession, rival_factory, voice: Voice, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = await create_session(db_session, project_id=TABLET_TEAM, pericope=P, language="pt")
    guide = the_guide_is(monkeypatch, Guide(lines=(OPENING, OPENING)))
    guide.first_fails = True

    async with (
        rival_factory() as one,
        rival_factory() as two,
        rival_factory() as three,
        room_client(one, monkeypatch) as failing_tablet,
        room_client(two, monkeypatch) as waiting_tablet,
        room_client(three, monkeypatch) as next_tablet,
    ):
        failing = asyncio.create_task(ask_for_the_opening(failing_tablet, session.id, "abre"))
        await asyncio.wait_for(guide.thinking.wait(), timeout=5)
        waiting = asyncio.create_task(ask_for_the_opening(waiting_tablet, session.id, "espera"))
        await asyncio.wait({waiting}, timeout=1)
        assert not waiting.done(), waiting.result().text[:300]
        guide.answer.set()
        failed, waited = await asyncio.wait_for(asyncio.gather(failing, waiting), timeout=10)

        assert failed.status_code == 502, failed.text[:300]
        assert waited.status_code == 502, waited.text[:300]
        assert waited.json()["code"] == "UPSTREAM_ERROR"
        assert await conversation(rival_factory, session.id) == []
        async with rival_factory() as fresh:
            remembered = (await fresh.execute(select(IRTurn))).scalars().all()
        assert remembered == [], "um pedido que nao foi respondido deixou uma resposta guardada"

        again = await asyncio.wait_for(
            ask_for_the_opening(next_tablet, session.id, "de-novo"), timeout=10
        )

    assert again.status_code == 200, again.text[:300]
    assert again.json()["audio_url"] == clip_url(clip_of(OPENING), session_id=session.id)
    assert await conversation(rival_factory, session.id) == [
        ("team", NOTE_PT_P03),
        ("guide", OPENING),
    ]


async def test_an_opening_claimed_by_a_request_on_another_instance_is_waited_for_not_drafted_again(
    db_session: AsyncSession, rival_factory, voice: Voice, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = await create_session(db_session, project_id=TABLET_TEAM, pericope=P, language="pt")
    guide = the_guide_is(monkeypatch, Guide())
    await claim_on_the_row(rival_factory, session.id, "outra-instancia", datetime.now(UTC))
    stored = TurnResponse(
        session_id=session.id,
        audio_url=clip_url("tts/voice/da-outra-instancia.mp3"),
        coverage=coverage_view(session),
        done=False,
        turn_id="outra-instancia",
    ).model_dump(mode="json")

    async with rival_factory() as one, room_client(one, monkeypatch) as tablet:
        asking = asyncio.create_task(ask_for_the_opening(tablet, session.id, "deste-tablet"))
        await asyncio.wait({asking}, timeout=1)
        assert not asking.done(), asking.result().text[:300]
        async with rival_factory() as other_instance:
            drafted = await get_session(other_instance, session.id)
            await append_opening(other_instance, drafted, guide_response=OPENING, commit=False)
            await remember_turn(
                other_instance, session_id=session.id, turn_id="outra-instancia", response=stored
            )
            await other_instance.commit()
        answered = await asyncio.wait_for(asking, timeout=10)

    assert answered.status_code == 200, answered.text[:300]
    assert answered.json() == {**stored, "turn_id": "deste-tablet"}
    assert guide.asked == 0, "a abertura reivindicada por outra instancia foi redigida de novo"
    assert await conversation(rival_factory, session.id) == [
        ("team", NOTE_PT_P03),
        ("guide", OPENING),
    ]


async def test_a_claim_left_by_a_holder_that_died_is_taken_over(
    db_session: AsyncSession, rival_factory, voice: Voice, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = await create_session(db_session, project_id=TABLET_TEAM, pericope=P, language="pt")
    guide = the_guide_is(monkeypatch, Guide())
    guide.answer.set()
    died_at = datetime.now(UTC) - dead_after() - timedelta(seconds=5)
    await claim_on_the_row(rival_factory, session.id, "morreu", died_at)

    async with rival_factory() as one, room_client(one, monkeypatch) as tablet:
        answered = await asyncio.wait_for(
            ask_for_the_opening(tablet, session.id, "assume"), timeout=10
        )

    assert answered.status_code == 200, answered.text[:300]
    assert guide.asked == 1
    assert await conversation(rival_factory, session.id) == [
        ("team", NOTE_PT_P03),
        ("guide", OPENING),
    ]


async def test_claiming_the_opening_does_not_count_as_the_teams_activity(
    db_session: AsyncSession, rival_factory, voice: Voice, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = await create_session(db_session, project_id=TABLET_TEAM, pericope=P, language="pt")
    guide = the_guide_is(monkeypatch, Guide())
    last_active = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
    async with rival_factory() as setup:
        await setup.execute(
            update(IRSession).where(IRSession.id == session.id).values(updated_at=last_active)
        )
        await setup.commit()
        before = await get_session(setup, session.id)
        version_before = before.version
    died_at = datetime.now(UTC) - dead_after() - timedelta(seconds=5)
    await claim_on_the_row(rival_factory, session.id, "morreu", died_at)

    async with rival_factory() as one, room_client(one, monkeypatch) as tablet:
        asking = asyncio.create_task(ask_for_the_opening(tablet, session.id, "assume"))
        await asyncio.wait_for(guide.thinking.wait(), timeout=5)
        async with rival_factory() as fresh:
            claimed = await get_session(fresh, session.id)
            updated_at, version = claimed.updated_at, claimed.version
        guide.answer.set()
        await asyncio.wait_for(asking, timeout=10)

    assert updated_at == last_active, "reivindicar a abertura marcou a sessao como ativa"
    assert version == version_before, "reivindicar a abertura mudou a versao da conversa"


async def test_a_prepared_line_is_never_parked_on_a_resumed_session_where_the_team_has_spoken(
    db_session: AsyncSession, rival_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = a_scripted_room(monkeypatch)

    async def _nothing(*_: Any, **__: Any) -> None:
        return None

    monkeypatch.setattr(sessions_api, "prepare_opening", _nothing)
    _, tablet = await a_claimed_device(db_session)

    async with room_client(db_session, monkeypatch, per_request=rival_factory) as client:
        passage = await the_tablet_opens(client, tablet, {"pericope": P, "language": "pt"})
        await the_room_opens(client, tablet, passage["session_id"])
        await the_team_says(client, script, tablet, passage["session_id"], SAID)
        panorama = await the_tablet_opens(client, tablet, {"pericope": "OV", "language": "pt"})
        async with rival_factory() as background:
            ready = await get_session(background, panorama["session_id"])
            ready.prepared_speech = "A primeira fala da passagem, escrita durante o panorama."
            ready.prepared_audio_key = "tts/voice/preparada.mp3"
            ready.prepared_pericope = P
            await background.commit()

        resumed = await the_tablet_opens(
            client,
            tablet,
            {"pericope": P, "language": "pt", "after_session": panorama["session_id"]},
        )

    assert resumed["session_id"] == passage["session_id"]
    async with rival_factory() as fresh:
        reread = await get_session(fresh, resumed["session_id"])
    assert reread.prepared_speech is None, "uma fala preparada ficou parada numa sessao com turnos"
    assert reread.prepared_audio_key is None


async def test_a_no_audio_request_with_a_new_turn_id_on_a_session_with_messages_hears_the_last_line_again(  # noqa: E501
    db_session: AsyncSession, rival_factory, voice: Voice, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = await create_session(db_session, project_id=TABLET_TEAM, pericope=P, language="pt")
    guide = the_guide_is(monkeypatch, Guide())
    guide.answer.set()

    async with rival_factory() as one, room_client(one, monkeypatch) as tablet:
        opened = await ask_for_the_opening(tablet, session.id, "abre")
        assert opened.status_code == 200, opened.text[:300]
        spoken = await speak(tablet, session.id, "fala")
        assert spoken.status_code == 200, spoken.text[:300]
        asked, before = guide.asked, await conversation(rival_factory, session.id)

        again = await ask_for_the_opening(tablet, session.id, "volta")

    assert again.status_code == 200, again.text[:300]
    assert again.json()["audio_url"] == clip_url(clip_of(REPLY), session_id=session.id)
    assert guide.asked == asked, "voltar a uma sessao com conversa chamou o Guia"
    assert await conversation(rival_factory, session.id) == before


async def test_an_opening_that_fails_after_it_was_written_leaves_the_claim_free(
    db_session: AsyncSession, rival_factory, voice: Voice, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The holder's own transaction already holds the row when the failure comes after the
    opening was written and before it was committed; freeing the claim must not wait on it."""
    session = await create_session(db_session, project_id=TABLET_TEAM, pericope=P, language="pt")
    guide = the_guide_is(monkeypatch, Guide(lines=(OPENING, OPENING)))
    guide.answer.set()

    async def the_store_is_down(*_: Any, **__: Any) -> None:
        raise UpstreamServiceError("o banco nao guardou a resposta")

    with monkeypatch.context() as failing:
        failing.setattr(sessions_api, "remember_turn", the_store_is_down)
        async with rival_factory() as one, room_client(one, monkeypatch) as tablet:
            failed = await asyncio.wait_for(
                ask_for_the_opening(tablet, session.id, "abre"), timeout=20
            )
    assert failed.status_code == 502, failed.text[:300]
    async with rival_factory() as fresh:
        claim = await fresh.scalar(
            select(IRSession.opening_claim_turn_id).where(IRSession.id == session.id)
        )
    assert claim is None, "a abertura que falhou depois de escrita deixou a reivindicacao presa"

    async with rival_factory() as two, room_client(two, monkeypatch) as tablet:
        again = await asyncio.wait_for(
            ask_for_the_opening(tablet, session.id, "de-novo"), timeout=20
        )

    assert again.status_code == 200, again.text[:300]
    assert await conversation(rival_factory, session.id) == [
        ("team", NOTE_PT_P03),
        ("guide", OPENING),
    ]
