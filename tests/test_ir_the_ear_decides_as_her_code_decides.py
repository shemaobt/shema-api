"""What the room makes of a take is what her `decideTeamUtterance` makes of it.

Scribe's answer enters as the JSON it sends, and the take as a WAV of known length that the
room measures itself. What is observed is what reaches the Guide: her note, the team's
words, or line D with no model called at all.
"""

from __future__ import annotations

import importlib
import io
import wave
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.services.internalization_room.hearing import heard_speech
from app.services.internalization_room.live_turn import run_comprehension_turn
from app.services.internalization_room.run_turn import TurnOutcome
from app.services.internalization_room.sessions import create_session
from tests.turn_harness import GUIDE, VALIDATOR, FakeAgent, P, settings, the_agent_answers

WELCOME = "Que bom que vocês ensaiaram. Me contem em português o que vocês disseram."
NOTE_PT_6 = (
    "[A equipe falou na língua materna por cerca de 6 segundos; sem transcrição — nenhuma "
    "palavra chegou até você.]"
)


def _take(seconds: float) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as take:
        take.setnchannels(1)
        take.setsampwidth(2)
        take.setframerate(8000)
        take.writeframes(b"\x00\x00" * int(8000 * seconds))
    return buffer.getvalue()


def _scribe_answers(monkeypatch: pytest.MonkeyPatch, status: int, payload: dict[str, Any]) -> None:
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _request: httpx.Response(status, json=payload))
    )
    scribe = importlib.import_module("app.services.translation_helper.transcribe_audio")
    monkeypatch.setattr(scribe, "_make_client", lambda: client)


@pytest.fixture
def agent(monkeypatch: pytest.MonkeyPatch) -> FakeAgent:
    return the_agent_answers(
        monkeypatch, FakeAgent(verdicts=[{"verdict": "pass", "issues": []}], drafts=[WELCOME])
    )


async def _the_room_hears(db_session: AsyncSession, audio: bytes) -> TurnOutcome:
    session = await create_session(db_session, language="pt", pericope=P)
    speech = await heard_speech(
        audio,
        filename="take.wav",
        language="pt",
        settings=Settings(database_url="sqlite+aiosqlite:///./test.db", elevenlabs_api_key="k"),
    )
    return await run_comprehension_turn(
        db_session,
        session,
        speech=speech,
        opening=False,
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        settings=settings(),
    )


async def test_portuguese_the_recognizer_is_forty_percent_sure_of_reaches_the_guide_as_words(
    db_session: AsyncSession, agent: FakeAgent, monkeypatch: pytest.MonkeyPatch
) -> None:
    _scribe_answers(
        monkeypatch,
        200,
        {"text": "Entendemos tudo.", "language_code": "por", "language_probability": 0.40},
    )

    outcome = await _the_room_hears(db_session, _take(6))

    assert agent.guide_inputs == ["Entendemos tudo."]
    assert outcome.transcript == "Entendemos tudo."
    assert outcome.room_note == ""


async def test_portuguese_the_recognizer_is_thirty_percent_sure_of_is_the_mother_tongue(
    db_session: AsyncSession, agent: FakeAgent, monkeypatch: pytest.MonkeyPatch
) -> None:
    _scribe_answers(
        monkeypatch,
        200,
        {"text": "Entendemos tudo.", "language_code": "por", "language_probability": 0.30},
    )

    outcome = await _the_room_hears(db_session, _take(6))

    assert agent.guide_inputs == [NOTE_PT_6], (
        "o Guia recebia como fala da equipe o português que o reconhecedor mal acreditava ter "
        "ouvido"
    )
    assert outcome.transcript == ""
    assert outcome.room_note == NOTE_PT_6


async def test_one_word_heard_as_guarani_at_half_confidence_is_the_mother_tongue_not_a_word(
    db_session: AsyncSession, agent: FakeAgent, monkeypatch: pytest.MonkeyPatch
) -> None:
    _scribe_answers(
        monkeypatch,
        200,
        {"text": "Kalivono", "language_code": "grn", "language_probability": 0.50},
    )

    outcome = await _the_room_hears(db_session, _take(6))

    assert agent.guide_inputs == [NOTE_PT_6], (
        "uma palavra de outra língua abaixo de 0,98 chegava ao Guia como palavra inventada"
    )
    assert outcome.room_note == NOTE_PT_6


async def test_a_confident_portuguese_word_the_recognizer_spelled_uncertainly_is_a_word_not_d(
    db_session: AsyncSession, agent: FakeAgent, monkeypatch: pytest.MonkeyPatch
) -> None:
    _scribe_answers(
        monkeypatch,
        200,
        {
            "text": "Pronto.",
            "language_code": "por",
            "language_probability": 0.90,
            "words": [{"text": "Pronto.", "type": "word", "logprob": -3.0}],
        },
    )

    outcome = await _the_room_hears(db_session, _take(2))

    assert agent.guide_inputs == ["Pronto."], (
        "a confiança por palavra baixa mandava a linha D a uma equipe que disse 'pronto'"
    )
    assert outcome.fixed_line == ""
    assert outcome.used_fail_safe is False
