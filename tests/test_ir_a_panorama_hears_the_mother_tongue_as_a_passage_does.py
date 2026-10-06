"""A Panorama turn is heard by the passage's rule, not by whether the recognizer wrote words.

A short take with no words hears her first D line and the Guide is not called; a take in another
language, under the mother-tongue floor, or with no words for twenty seconds reaches the Guide as
her note, never as the recognizer's words, and the Validator never reads that note as the team's
own speech. The turn's record keeps what the room heard, as a passage turn's does.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession
from app.services import internalization_room as room
from app.services.internalization_room.sessions import create_session
from tests.hearing_harness import (
    nothing_settles,
    the_take_lasts,
    the_transcriber_hears,
    the_transcriber_hears_no_words,
)
from tests.release_harness import KEY, PREFIX
from tests.room_harness import room_client, the_room_speaks
from tests.text_seam_harness import GUIDE_LINE, ScriptedAgent, the_models_answer
from tests.turn_harness import the_room_agent_is

PANORAMA = "OV-Ruth"
PORTUGUESE = "Noemi voltou para Belém com Rute no tempo da colheita"
ENGLISH = "Naomi went back to Bethlehem with Ruth at the harvest"
AN_ENGLISH_LINE = "Welcome. Tell me what you remember about this book."
TERENA_AS_SPANISH = "koeti yoko vitukeovo enepone itukovo"
D0 = "D0"


def _note(seconds: int) -> str:
    return (
        f"[A equipe falou na língua materna por cerca de {seconds} segundos; sem transcrição — "
        "nenhuma palavra chegou até você.]"
    )


class RecordingValidator(ScriptedAgent):
    """The scripted models, keeping the system prompt the Validator was handed each time."""

    def __init__(self) -> None:
        super().__init__([])
        self.validator_systems: list[str] = []

    async def __call__(self, *, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        if "corrected_response" in system_prompt:
            self.validator_systems.append(system_prompt)
            return json.dumps({"verdict": "pass", "issues": []})
        return await super().__call__(
            system_prompt=system_prompt, user_content=user_content, **kwargs
        )


@pytest.fixture
def guide(monkeypatch: pytest.MonkeyPatch) -> ScriptedAgent:
    return the_models_answer(monkeypatch)


@pytest.fixture
async def tablet(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, guide: ScriptedAgent
) -> AsyncIterator[httpx.AsyncClient]:
    the_room_speaks(monkeypatch)
    the_room_agent_is(monkeypatch, turn=guide)
    nothing_settles(monkeypatch)
    async with room_client(db_session, monkeypatch) as client:
        yield client


async def _an_open_panorama(
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    language: str = "pt",
) -> IRSession:
    session = await create_session(db_session, language=language, pericope=PANORAMA)
    opened = await tablet.post(f"{PREFIX}/sessions/{session.id}/turns", headers={"X-Room-Key": KEY})
    assert opened.status_code == 200, opened.text
    guide.guide_inputs.clear()
    return session


async def _the_team_sends_a_take(tablet: httpx.AsyncClient, session: IRSession) -> dict[str, Any]:
    answered = await tablet.post(
        f"{PREFIX}/sessions/{session.id}/turns",
        headers={"X-Room-Key": KEY},
        files={"file": ("ensaio.m4a", b"audio", "audio/m4a")},
    )
    assert answered.status_code == 200, answered.text
    reply: dict[str, Any] = answered.json()
    return reply


async def _the_conversation(db_session: AsyncSession, session_id: str) -> list[dict[str, Any]]:
    db_session.expire_all()
    stored = await room.get_session(db_session, session_id)
    return list(stored.messages)


async def test_a_3_second_take_with_no_words_in_a_panorama_is_answered_with_d_1_and_the_guide_is_not_called(  # noqa: E501
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_panorama(db_session, tablet, guide)
    the_transcriber_hears_no_words(monkeypatch)
    the_take_lasts(monkeypatch, 3_000)

    reply = await _the_team_sends_a_take(tablet, session)

    assert reply["fixed_line"] == D0
    assert guide.guide_inputs == []


async def test_three_3_second_takes_with_no_words_in_a_row_in_a_panorama_each_hear_d_1(
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_panorama(db_session, tablet, guide)
    the_transcriber_hears_no_words(monkeypatch)
    the_take_lasts(monkeypatch, 3_000)

    heard = [(await _the_team_sends_a_take(tablet, session))["fixed_line"] for _ in range(3)]

    assert heard == [D0, D0, D0]


async def test_a_terena_take_the_transcriber_labels_as_spanish_at_0_7_reaches_the_panorama_guide_as_the_mother_tongue_note(  # noqa: E501
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_panorama(db_session, tablet, guide)
    the_transcriber_hears(monkeypatch, TERENA_AS_SPANISH, "spa", 0.7)
    the_take_lasts(monkeypatch, 40_000)

    await _the_team_sends_a_take(tablet, session)

    assert guide.guide_inputs == [_note(40)], (
        "o Guia do Panorama recebia o espanhol inventado pelo reconhecedor como palavras"
    )


async def test_a_25_second_take_with_no_recognized_words_in_a_panorama_reaches_the_guide_as_the_mother_tongue_note_saying_25_seconds(  # noqa: E501
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_panorama(db_session, tablet, guide)
    the_transcriber_hears_no_words(monkeypatch)
    the_take_lasts(monkeypatch, 25_000)

    reply = await _the_team_sends_a_take(tablet, session)

    assert guide.guide_inputs == [_note(25)]
    assert reply["fixed_line"] == ""


async def test_portuguese_heard_at_0_30_in_a_portuguese_panorama_reaches_the_guide_as_the_mother_tongue_note(  # noqa: E501
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_panorama(db_session, tablet, guide)
    the_transcriber_hears(monkeypatch, PORTUGUESE, "pt", 0.30)
    the_take_lasts(monkeypatch, 15_000)

    await _the_team_sends_a_take(tablet, session)

    assert guide.guide_inputs == [_note(15)]


async def test_clear_portuguese_at_0_9_in_a_panorama_reaches_the_guide_as_the_teams_words(
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_panorama(db_session, tablet, guide)
    the_transcriber_hears(monkeypatch, PORTUGUESE, "pt", 0.9)
    the_take_lasts(monkeypatch, 12_000)

    reply = await _the_team_sends_a_take(tablet, session)

    assert guide.guide_inputs == [PORTUGUESE]
    assert reply["fixed_line"] == ""


async def test_english_speech_in_an_english_panorama_reaches_the_guide_as_the_teams_words(
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    english = the_models_answer(
        monkeypatch,
        AN_ENGLISH_LINE,
        json.dumps({"verdict": "pass", "issues": []}),
        AN_ENGLISH_LINE,
    )
    session = await _an_open_panorama(db_session, tablet, english, language="en")
    the_transcriber_hears(monkeypatch, ENGLISH, "eng", 0.9)
    the_take_lasts(monkeypatch, 12_000)

    await _the_team_sends_a_take(tablet, session)

    assert english.guide_inputs == [ENGLISH]


async def test_a_panorama_mother_tongue_turn_is_never_handed_to_the_validator_as_the_teams_words(
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    models = RecordingValidator()
    the_room_agent_is(monkeypatch, turn=models)
    session = await _an_open_panorama(db_session, tablet, models)
    the_transcriber_hears(monkeypatch, TERENA_AS_SPANISH, "spa", 0.7)
    the_take_lasts(monkeypatch, 40_000)
    models.validator_systems.clear()

    await _the_team_sends_a_take(tablet, session)

    assert models.guide_inputs == [_note(40)]
    assert len(models.validator_systems) == 1
    judged = models.validator_systems[0]
    assert "língua materna" not in judged
    assert "[A equipe" not in judged
    assert TERENA_AS_SPANISH not in judged


async def test_a_panorama_mother_tongue_turn_keeps_the_note_as_the_rooms_entry_and_writes_no_team_entry(  # noqa: E501
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_panorama(db_session, tablet, guide)
    before = len(await _the_conversation(db_session, session.id))
    the_transcriber_hears(monkeypatch, TERENA_AS_SPANISH, "spa", 0.7)
    the_take_lasts(monkeypatch, 40_000)

    await _the_team_sends_a_take(tablet, session)

    written = (await _the_conversation(db_session, session.id))[before:]
    assert [(entry["role"], entry["text"]) for entry in written] == [
        ("room", _note(40)),
        ("guide", GUIDE_LINE),
    ]


async def test_a_panorama_turns_record_keeps_the_language_its_probability_the_mother_tongue_decision_and_the_takes_length(  # noqa: E501
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_panorama(db_session, tablet, guide)
    the_transcriber_hears(monkeypatch, TERENA_AS_SPANISH, "es", 0.7)
    the_take_lasts(monkeypatch, 40_000)

    await _the_team_sends_a_take(tablet, session)

    guide_entry = (await _the_conversation(db_session, session.id))[-1]
    assert {
        key: guide_entry.get(key, "absent")
        for key in ("language", "language_probability", "mother_tongue", "take_ms")
    } == {"language": "es", "language_probability": 0.7, "mother_tongue": True, "take_ms": 40_000}
