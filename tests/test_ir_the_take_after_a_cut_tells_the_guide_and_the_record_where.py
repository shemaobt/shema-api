"""The take after a cut tells the Guide with her interruption note, and the record where.

The tablet door accepts Marcia's three multipart fields for a cut. The note comes ahead of the
mother-tongue note or the team's words, a cut followed by nothing heard is a miss answered with
the D line, and the turn's guide entry keeps where the cut fell. Positions that are negative or
sent without the flag are never a refusal and never a cut.
"""

from __future__ import annotations

import copy
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession
from app.services import internalization_room as room
from app.services.internalization_room.sessions import create_session
from tests.device_harness import TABLET_TEAM
from tests.hearing_harness import (
    nothing_settles,
    the_take_lasts,
    the_transcriber_hears,
    the_transcriber_hears_no_words,
    the_transcriber_refuses,
)
from tests.release_harness import PREFIX
from tests.room_harness import Room, room_client, the_room_speaks
from tests.text_seam_harness import ScriptedAgent, the_models_answer
from tests.turn_harness import P, the_room_agent_is

PORTUGUESE = "Noemi voltou para Belém com Rute no tempo da colheita"
TERENA_AS_SPANISH = "koeti yoko vitukeovo enepone itukovo"
CUT = "[A equipe interrompeu a sua fala anterior neste ponto.]"


def _mother_tongue(seconds: int) -> str:
    return (
        f"[A equipe falou na língua materna por cerca de {seconds} segundos; sem transcrição — "
        "nenhuma palavra chegou até você.]"
    )


@pytest.fixture
def guide(monkeypatch: pytest.MonkeyPatch) -> ScriptedAgent:
    return the_models_answer(monkeypatch)


@pytest.fixture
def voiced(monkeypatch: pytest.MonkeyPatch) -> Room:
    return the_room_speaks(monkeypatch)


@pytest.fixture
async def tablet(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    guide: ScriptedAgent,
    voiced: Room,
) -> AsyncIterator[httpx.AsyncClient]:
    the_room_agent_is(monkeypatch, turn=guide)
    nothing_settles(monkeypatch)
    async with room_client(db_session, monkeypatch) as client:
        yield client


async def _an_open_session(
    db_session: AsyncSession, tablet: httpx.AsyncClient, guide: ScriptedAgent, voiced: Room
) -> IRSession:
    session = await create_session(db_session, project_id=TABLET_TEAM, language="pt", pericope=P)
    opened = await tablet.post(f"{PREFIX}/sessions/{session.id}/turns")
    assert opened.status_code == 200, opened.text
    guide.guide_inputs.clear()
    voiced.said.clear()
    return session


async def _the_team_sends_a_take(
    tablet: httpx.AsyncClient, session: IRSession, **fields: str
) -> dict[str, Any]:
    answered = await tablet.post(
        f"{PREFIX}/sessions/{session.id}/turns",
        files={"file": ("ensaio.m4a", b"audio", "audio/m4a")},
        data=fields,
    )
    assert answered.status_code == 200, answered.text
    reply: dict[str, Any] = answered.json()
    return reply


async def _the_conversation(db_session: AsyncSession, session_id: str) -> list[dict[str, Any]]:
    db_session.expire_all()
    stored = await room.get_session(db_session, session_id)
    return copy.deepcopy(list(stored.messages))


async def _the_turns_record(db_session: AsyncSession, session_id: str) -> dict[str, Any]:
    return (await _the_conversation(db_session, session_id))[-1]


async def test_a_terena_take_of_about_12_seconds_hands_the_guide_her_note_saying_12_and_that_no_word_reached_it(  # noqa: E501
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    voiced: Room,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_session(db_session, tablet, guide, voiced)
    the_transcriber_hears(monkeypatch, TERENA_AS_SPANISH, "spa", 0.7)
    the_take_lasts(monkeypatch, 12_000)

    await _the_team_sends_a_take(tablet, session)

    assert guide.guide_inputs == [_mother_tongue(12)]


async def test_the_team_never_hears_the_mother_tongue_note(
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    voiced: Room,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_session(db_session, tablet, guide, voiced)
    the_transcriber_hears(monkeypatch, TERENA_AS_SPANISH, "spa", 0.7)
    the_take_lasts(monkeypatch, 12_000)

    await _the_team_sends_a_take(tablet, session)

    assert voiced.said
    assert not any("nenhuma palavra chegou até você" in line for line in voiced.said)


async def test_a_take_sent_after_a_cut_hands_the_guide_her_interruption_note_before_the_teams_words(
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    voiced: Room,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_session(db_session, tablet, guide, voiced)
    the_transcriber_hears(monkeypatch, PORTUGUESE, "por", 0.95)
    the_take_lasts(monkeypatch, 6_000)

    await _the_team_sends_a_take(tablet, session, interrupted="1")

    assert guide.guide_inputs == [f"{CUT} {PORTUGUESE}"]


async def test_a_mother_tongue_take_sent_after_a_cut_hands_the_guide_the_interruption_note_then_the_mother_tongue_note(  # noqa: E501
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    voiced: Room,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_session(db_session, tablet, guide, voiced)
    the_transcriber_hears(monkeypatch, TERENA_AS_SPANISH, "spa", 0.7)
    the_take_lasts(monkeypatch, 30_000)

    await _the_team_sends_a_take(tablet, session, interrupted="1")

    assert guide.guide_inputs == [f"{CUT} {_mother_tongue(30)}"]


async def test_a_cut_followed_by_a_take_with_no_words_is_answered_with_d_1_and_the_guide_is_not_called(  # noqa: E501
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    voiced: Room,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_session(db_session, tablet, guide, voiced)
    the_transcriber_hears_no_words(monkeypatch)
    the_take_lasts(monkeypatch, 8_000)

    reply = await _the_team_sends_a_take(tablet, session, interrupted="1")

    assert reply["fixed_line"] == "D0"
    assert guide.guide_inputs == []


async def test_a_cut_followed_by_a_take_the_recognizer_refused_is_answered_with_d_1(
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    voiced: Room,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_session(db_session, tablet, guide, voiced)
    the_transcriber_refuses(monkeypatch)
    the_take_lasts(monkeypatch, 8_000)

    reply = await _the_team_sends_a_take(tablet, session, interrupted="1")

    assert reply["fixed_line"] == "D0"
    assert guide.guide_inputs == []


async def test_a_cut_followed_by_25_seconds_with_no_words_hands_the_guide_both_notes(
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    voiced: Room,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_session(db_session, tablet, guide, voiced)
    the_transcriber_hears_no_words(monkeypatch)
    the_take_lasts(monkeypatch, 25_000)

    reply = await _the_team_sends_a_take(tablet, session, interrupted="1")

    assert guide.guide_inputs == [f"{CUT} {_mother_tongue(25)}"]
    assert reply["fixed_line"] == ""


async def test_the_record_of_the_take_after_a_cut_keeps_where_the_cut_fell(
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    voiced: Room,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_session(db_session, tablet, guide, voiced)
    the_transcriber_hears(monkeypatch, PORTUGUESE, "por", 0.95)
    the_take_lasts(monkeypatch, 6_000)

    await _the_team_sends_a_take(
        tablet, session, interrupted="1", interrupted_at_ms="4200", interrupted_of_ms="9000"
    )

    record = await _the_turns_record(db_session, session.id)
    assert record["interrupted"] == {"at_ms": 4200, "of_ms": 9000}


async def test_a_cut_with_no_positions_is_kept_at_0_of_an_unknown_length(
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    voiced: Room,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_session(db_session, tablet, guide, voiced)
    the_transcriber_hears(monkeypatch, PORTUGUESE, "por", 0.95)
    the_take_lasts(monkeypatch, 6_000)

    await _the_team_sends_a_take(tablet, session, interrupted="1")

    record = await _the_turns_record(db_session, session.id)
    assert record["interrupted"] == {"at_ms": 0, "of_ms": None}


async def test_the_record_of_a_cut_followed_by_nothing_heard_still_keeps_where_the_cut_fell(
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    voiced: Room,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_session(db_session, tablet, guide, voiced)
    the_transcriber_hears_no_words(monkeypatch)
    the_take_lasts(monkeypatch, 8_000)

    await _the_team_sends_a_take(
        tablet, session, interrupted="1", interrupted_at_ms="4200", interrupted_of_ms="9000"
    )

    record = await _the_turns_record(db_session, session.id)
    assert record["fixed_line"] == "D0"
    assert record["interrupted"] == {"at_ms": 4200, "of_ms": 9000}


async def test_a_take_that_followed_no_cut_has_no_interrupted_key_in_its_record(
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    voiced: Room,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_session(db_session, tablet, guide, voiced)
    the_transcriber_hears(monkeypatch, PORTUGUESE, "por", 0.95)
    the_take_lasts(monkeypatch, 6_000)

    await _the_team_sends_a_take(tablet, session)

    record = await _the_turns_record(db_session, session.id)
    assert "interrupted" not in record


async def test_positions_sent_without_the_interrupted_flag_are_not_a_cut(
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    voiced: Room,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_session(db_session, tablet, guide, voiced)
    the_transcriber_hears(monkeypatch, PORTUGUESE, "por", 0.95)
    the_take_lasts(monkeypatch, 6_000)

    await _the_team_sends_a_take(tablet, session, interrupted_at_ms="4200")

    assert guide.guide_inputs == [PORTUGUESE]
    record = await _the_turns_record(db_session, session.id)
    assert "interrupted" not in record


async def test_the_cut_reply_stays_whole_in_the_conversation(
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    voiced: Room,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_session(db_session, tablet, guide, voiced)
    before = await _the_conversation(db_session, session.id)
    before_count = len(before)
    cut_reply = before[-1]
    the_transcriber_hears(monkeypatch, PORTUGUESE, "por", 0.95)
    the_take_lasts(monkeypatch, 6_000)

    await _the_team_sends_a_take(
        tablet, session, interrupted="1", interrupted_at_ms="4200", interrupted_of_ms="9000"
    )

    after = await _the_conversation(db_session, session.id)
    assert after[before_count - 1] == cut_reply
    assert "interrupted" not in after[before_count - 1]


async def test_a_negative_cut_position_counts_as_absent_and_the_take_is_still_a_cut(
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    voiced: Room,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_session(db_session, tablet, guide, voiced)
    the_transcriber_hears(monkeypatch, PORTUGUESE, "por", 0.95)
    the_take_lasts(monkeypatch, 6_000)

    await _the_team_sends_a_take(
        tablet, session, interrupted="1", interrupted_at_ms="-1", interrupted_of_ms="-5"
    )

    assert guide.guide_inputs == [f"{CUT} {PORTUGUESE}"]
    record = await _the_turns_record(db_session, session.id)
    assert record["interrupted"] == {"at_ms": 0, "of_ms": None}


@pytest.mark.parametrize(
    ("at_ms", "of_ms", "kept"),
    [
        ("abc", "4200.6", {"at_ms": 0, "of_ms": 4201}),
        ("4200.5", "", {"at_ms": 4201, "of_ms": 0}),
        ("1_000", "1_000", {"at_ms": 0, "of_ms": None}),
    ],
)
async def test_an_unreadable_cut_position_counts_as_absent_and_the_take_is_still_a_cut(
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    voiced: Room,
    monkeypatch: pytest.MonkeyPatch,
    at_ms: str,
    of_ms: str,
    kept: dict[str, int | None],
) -> None:
    session = await _an_open_session(db_session, tablet, guide, voiced)
    the_transcriber_hears(monkeypatch, PORTUGUESE, "por", 0.95)
    the_take_lasts(monkeypatch, 6_000)

    await _the_team_sends_a_take(
        tablet, session, interrupted="1", interrupted_at_ms=at_ms, interrupted_of_ms=of_ms
    )

    assert guide.guide_inputs == [f"{CUT} {PORTUGUESE}"]
    record = await _the_turns_record(db_session, session.id)
    assert record["interrupted"] == kept


async def test_the_houses_truthy_words_for_the_interrupted_flag_are_a_cut(
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    voiced: Room,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_session(db_session, tablet, guide, voiced)
    the_transcriber_hears(monkeypatch, PORTUGUESE, "por", 0.95)
    the_take_lasts(monkeypatch, 6_000)

    await _the_team_sends_a_take(tablet, session, interrupted="True")

    assert guide.guide_inputs == [f"{CUT} {PORTUGUESE}"]
    record = await _the_turns_record(db_session, session.id)
    assert record["interrupted"] == {"at_ms": 0, "of_ms": None}


async def test_an_interrupted_flag_that_is_not_a_truthy_word_is_no_cut_and_the_take_is_still_answered(  # noqa: E501
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    voiced: Room,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_session(db_session, tablet, guide, voiced)
    the_transcriber_hears(monkeypatch, PORTUGUESE, "por", 0.95)
    the_take_lasts(monkeypatch, 6_000)

    await _the_team_sends_a_take(tablet, session, interrupted="abc", interrupted_at_ms="4200")

    assert guide.guide_inputs == [PORTUGUESE]
    record = await _the_turns_record(db_session, session.id)
    assert "interrupted" not in record
