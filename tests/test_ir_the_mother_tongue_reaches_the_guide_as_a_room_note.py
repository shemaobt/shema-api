"""A rehearsal in the team's own language is a fact the Guide is handed, never words or a line."""

from __future__ import annotations

import sys
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.services import internalization_room as room
from app.services.internalization_room.canon.parse_map import load_map
from app.services.internalization_room.sessions import create_session
from app.services.internalization_room.turn.speech import speak_back
from tests.text_seam_harness import GUIDE_LINE, RUNNER_KEY, the_app, the_models_answer
from tests.turn_harness import GUIDE, VALIDATOR, FakeAgent, P, settings, the_agent_answers

SEAM = "/api/internalization-room/text-seam"

TERENA = "koeti yoko vitukeovo enepone itukovo"
NOTE_PT_40 = "[A equipe falou na língua materna por cerca de 40 segundos; sem transcrição]"
WELCOME = "Que bom que vocês ensaiaram. Me contem em português o que vocês disseram."


@pytest.fixture
def agent(monkeypatch: pytest.MonkeyPatch) -> FakeAgent:
    return the_agent_answers(
        monkeypatch, FakeAgent(verdicts=[{"verdict": "pass", "issues": []}], drafts=[WELCOME])
    )


async def _speak(session: Any, **overrides: Any) -> Any:
    given: dict[str, Any] = {
        "mother_tongue": False,
        "take_ms": None,
        "session": session,
        "messages": [{"role": "guide", "text": "Ensaiem a cena na língua de vocês."}],
        "transcript": "a fome chegou",
        "opening": False,
        "empty": False,
        "uncertain": False,
        "book": load_map(P).book,
        "guide_prompt": GUIDE,
        "validator_prompt": VALIDATOR,
        "pericope": P,
        "settings": settings(),
        "app_context": "",
    }
    return await speak_back(**{**given, **overrides})


async def test_a_rehearsal_in_the_teams_own_language_reaches_the_guide_as_a_note_not_a_line(
    db_session: AsyncSession, agent: FakeAgent
) -> None:
    session = await create_session(db_session, language="pt", pericope=P)

    outcome = await _speak(session, mother_tongue=True, take_ms=40_000, transcript=TERENA)

    assert agent.guide_inputs == [NOTE_PT_40], (
        "a sala respondia com a linha fixa G e o Guia nunca era chamado"
    )
    assert outcome.speech == WELCOME
    assert outcome.fixed_line == ""
    assert outcome.used_fail_safe is False
    assert outcome.transcript == "", (
        "as palavras inventadas pelo reconhecedor viajavam no resultado e viravam fala da equipe"
    )
    assert outcome.room_note == NOTE_PT_40


async def test_a_take_nobody_could_measure_is_still_a_rehearsal_only_without_its_length(
    db_session: AsyncSession, agent: FakeAgent
) -> None:
    session = await create_session(db_session, language="pt", pericope=P)

    outcome = await _speak(session, mother_tongue=True, take_ms=None, transcript=TERENA)

    assert agent.guide_inputs == ["[A equipe falou na língua materna; sem transcrição]"], (
        "a nota dizia 'por cerca de 0 segundos' quando o ffprobe não leu o áudio"
    )
    assert outcome.room_note == "[A equipe falou na língua materna; sem transcrição]"


async def test_an_english_room_hands_the_guide_the_note_in_english(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    agent = the_agent_answers(
        monkeypatch,
        FakeAgent(
            verdicts=[{"verdict": "pass", "issues": []}],
            drafts=["Good, you rehearsed it. Tell me in English what you said."],
        ),
    )
    session = await create_session(db_session, language="en", pericope=P)

    await _speak(session, mother_tongue=True, take_ms=41_000, transcript=TERENA)

    assert agent.guide_inputs == [
        "[The team spoke in their own language for about 41 seconds; no transcription]"
    ], "a sala em inglês entregava a nota em português e o Guia misturava as línguas"


async def test_only_a_take_in_another_language_is_measured_for_its_length(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    from app.core.config import Settings
    from app.services.internalization_room import hearing

    heard_language = {"code": "und"}

    async def _detailed(*_: object, **__: object) -> object:
        return SimpleNamespace(
            text=TERENA,
            language_code=heard_language["code"],
            language_probability=0.99,
            transcript_confidence=0.9,
        )

    measured: list[bytes] = []

    async def _measure(audio: bytes) -> int:
        measured.append(audio)
        return 41_000

    monkeypatch.setattr(hearing, "transcribe_audio_detailed", _detailed)
    monkeypatch.setattr(hearing, "measure_ms", _measure)
    settings = Settings(database_url="sqlite+aiosqlite:///./test.db")

    in_their_own = await hearing.heard_speech(b"terena", language="pt", settings=settings)
    heard_language["code"] = "pt"
    in_portuguese = await hearing.heard_speech(b"portugues", language="pt", settings=settings)

    assert in_their_own.take_ms == 41_000, (
        "a nota nunca dizia por quanto tempo a equipe falou: ninguém media o áudio"
    )
    assert in_portuguese.take_ms is None
    assert measured == [b"terena"], "um ffprobe rodava em cada turno, e não só no de língua materna"


async def test_words_the_room_could_not_make_out_draw_the_d_line_and_travel_no_further(
    db_session: AsyncSession, agent: FakeAgent
) -> None:
    session = await create_session(db_session, language="pt", pericope=P)

    outcome = await _speak(session, uncertain=True, transcript="mmm ne")

    assert outcome.fixed_line == "D1"
    assert outcome.degraded is True
    assert outcome.transcript == "", (
        "o palpite do reconhecedor viajava dentro da linha que pedia para repetir e era "
        "gravado como fala da equipe"
    )
    assert agent.guide_inputs == []


@pytest.fixture()
async def seam(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        get_settings(), "internalization_room_runner_key", RUNNER_KEY, raising=False
    )
    transport = ASGITransport(app=the_app(db_session))
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", headers={"X-Access-Code": RUNNER_KEY}
    ) as client:
        yield client


async def _an_open_session(client: httpx.AsyncClient) -> str:
    created = await client.post(
        f"{SEAM}/session", json={"pericopeId": "P01", "language": "Brazilian Portuguese"}
    )
    session_id = created.json()["sessionId"]
    await client.post(f"{SEAM}/turn", json={"sessionId": session_id, "kickoff": True})
    return session_id


async def test_the_note_is_kept_as_a_fact_about_the_room_never_as_words_the_team_said(
    seam: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    the_models_answer(monkeypatch)
    session_id = await _an_open_session(seam)

    answered = await seam.post(
        f"{SEAM}/turn", json={"sessionId": session_id, "text": TERENA, "motherTongue": 40}
    )

    assert answered.status_code == 200, answered.text
    session = await room.get_session(db_session, session_id)
    assert session.messages == [
        {"role": "guide", "text": GUIDE_LINE},
        {"role": "room", "text": NOTE_PT_40},
        {"role": "guide", "text": GUIDE_LINE},
    ], (
        "as palavras que o reconhecedor inventou ficavam na conversa como fala da equipe, e o "
        "Guia e o Validador as liam de volta no turno seguinte"
    )


async def test_the_next_turn_shows_the_guide_a_fact_about_the_room_on_the_teams_side(
    seam: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    the_models_answer(monkeypatch)
    session_id = await _an_open_session(seam)
    await seam.post(
        f"{SEAM}/turn", json={"sessionId": session_id, "text": TERENA, "motherTongue": 40}
    )
    heard: list[list[dict[str, str]]] = []

    async def _listening(*, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        if "corrected_response" in system_prompt:
            return '{"verdict": "pass", "issues": []}'
        heard.append(list(kwargs["conversation"]))
        return GUIDE_LINE

    monkeypatch.setattr(
        sys.modules["app.services.internalization_room.run_turn"], "call_agent", _listening
    )

    await seam.post(f"{SEAM}/turn", json={"sessionId": session_id, "text": "a fome chegou"})

    assert heard[0] == [
        {"role": "assistant", "text": GUIDE_LINE},
        {"role": "user", "text": NOTE_PT_40},
        {"role": "assistant", "text": GUIDE_LINE},
    ], "a nota da sala entrava no histórico como se o Guia a tivesse dito"
