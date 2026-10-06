"""A rehearsal in the team's own language is a fact the Guide is handed, never words or a line."""

from __future__ import annotations

import json
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
from tests.text_seam_harness import (
    BEARER,
    GOLDEN,
    GUIDE_LINE,
    RUNNER_KEY,
    the_app,
    the_models_answer,
)
from tests.turn_harness import (
    GUIDE,
    VALIDATOR,
    FakeAgent,
    P,
    settings,
    the_agent_answers,
    the_room_agent_is,
)

TERENA = "koeti yoko vitukeovo enepone itukovo"
NOTE_PT_40 = (
    "[A equipe falou na língua materna por cerca de 40 segundos; sem transcrição — nenhuma "
    "palavra chegou até você.]"
)
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
        "book": load_map(P).book,
        "guide_prompt": GUIDE,
        "validator_prompt": VALIDATOR,
        "pericope": P,
        "settings": settings(),
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

    unmeasured = (
        "[A equipe falou na língua materna; sem transcrição — nenhuma palavra chegou até você.]"
    )
    assert agent.guide_inputs == [unmeasured], (
        "a nota dizia 'por cerca de 0 segundos' quando o ffprobe não leu o áudio"
    )
    assert outcome.room_note == unmeasured


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
        "[The team spoke in their own language for about 41 seconds; no transcription — no "
        "words reached you.]"
    ], "a sala em inglês entregava a nota em português e o Guia misturava as línguas"


async def test_every_take_is_measured_for_its_length(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import Settings
    from app.services.internalization_room import hearing
    from app.services.translation_helper.transcribe_audio import TranscriptionResult

    heard_language = {"code": "und"}

    async def _detailed(*_: object, **__: object) -> TranscriptionResult:
        return TranscriptionResult(
            text=TERENA, language_code=heard_language["code"], language_probability=0.99
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
    assert in_portuguese.take_ms == 41_000, "um take em português ficava sem duração no registro"
    assert measured == [b"terena", b"portugues"]


async def test_a_take_with_no_words_draws_the_d_line_and_travels_no_further(
    db_session: AsyncSession, agent: FakeAgent
) -> None:
    session = await create_session(db_session, language="pt", pericope=P)

    outcome = await _speak(session, empty=True, transcript="")

    assert outcome.fixed_line == "D0"
    assert outcome.degraded is True
    assert outcome.transcript == ""
    assert agent.guide_inputs == []


def test_no_fixed_line_answers_the_mother_tongue_in_any_language_the_room_speaks() -> None:
    import re

    from app.services.internalization_room._default_prompts import fail_safe_utterances
    from app.services.internalization_room.fail_safe import FailSafe

    assert "G" not in {str(kind) for kind in FailSafe}, (
        "a família G seguia no catálogo depois de a Marcia a ter abolido"
    )
    assert re.findall(r"^### G(-[a-z]{2})?\.", fail_safe_utterances(), re.M) == [], (
        "o arquivo autorado ainda carregava a seção G, que o vendorizado dela não tem"
    )


@pytest.fixture()
async def seam(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        get_settings(), "internalization_room_runner_key", RUNNER_KEY, raising=False
    )
    transport = ASGITransport(app=the_app(db_session))
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", headers=BEARER
    ) as client:
        yield client


async def _an_open_session(client: httpx.AsyncClient) -> str:
    created = await client.post(
        f"{GOLDEN}/session", json={"pericopeId": "P01", "language": "Brazilian Portuguese"}
    )
    session_id = created.json()["sessionId"]
    await client.post(f"{GOLDEN}/turn", json={"sessionId": session_id, "roomNote": "session_start"})
    return session_id


async def test_the_note_is_kept_as_a_fact_about_the_room_never_as_words_the_team_said(
    seam: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    the_models_answer(monkeypatch)
    session_id = await _an_open_session(seam)

    answered = await seam.post(
        f"{GOLDEN}/turn", json={"sessionId": session_id, "roomNote": "mother_tongue", "seconds": 40}
    )

    assert answered.status_code == 200, answered.text
    session = await room.get_session(db_session, session_id)
    assert [(m["role"], m["text"]) for m in session.messages] == [
        ("guide", GUIDE_LINE),
        ("room", NOTE_PT_40),
        ("guide", GUIDE_LINE),
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
        f"{GOLDEN}/turn", json={"sessionId": session_id, "roomNote": "mother_tongue", "seconds": 40}
    )
    heard: list[list[dict[str, str]]] = []

    async def _listening(*, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        if "corrected_response" in system_prompt:
            return '{"verdict": "pass", "issues": []}'
        heard.append(list(kwargs["conversation"]))
        return GUIDE_LINE

    the_room_agent_is(monkeypatch, turn=_listening)

    await seam.post(f"{GOLDEN}/turn", json={"sessionId": session_id, "teamText": "a fome chegou"})

    assert heard[0] == [
        {"role": "assistant", "text": GUIDE_LINE},
        {"role": "user", "text": NOTE_PT_40},
        {"role": "assistant", "text": GUIDE_LINE},
    ], "a nota da sala entrava no histórico como se o Guia a tivesse dito"


async def test_the_validators_evidence_labels_the_room_note_room_never_team(
    seam: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    the_models_answer(monkeypatch)
    session_id = await _an_open_session(seam)
    await seam.post(
        f"{GOLDEN}/turn", json={"sessionId": session_id, "roomNote": "mother_tongue", "seconds": 40}
    )
    seen: list[str] = []

    async def _listening(*, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        if "corrected_response" in system_prompt:
            seen.append(system_prompt)
            return json.dumps({"verdict": "pass", "issues": []})
        return GUIDE_LINE

    the_room_agent_is(monkeypatch, turn=_listening)

    await seam.post(f"{GOLDEN}/turn", json={"sessionId": session_id, "teamText": "a fome chegou"})

    assert f"Room: {NOTE_PT_40}" in seen[0], (
        "o bloco de evidência para o Validador não rotulava o registro da sala como Room:"
    )
    assert f"Team: {NOTE_PT_40}" not in seen[0], (
        "a nota da sala era mostrada ao Validador como se a equipe a tivesse dito"
    )


async def test_the_mother_tongue_turn_hides_its_own_note_from_the_validators_team_utterance(
    seam: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    the_models_answer(monkeypatch)
    session_id = await _an_open_session(seam)
    seen: list[str] = []

    async def _listening(*, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        if "corrected_response" in system_prompt:
            seen.append(system_prompt)
            return json.dumps({"verdict": "pass", "issues": []})
        return GUIDE_LINE

    the_room_agent_is(monkeypatch, turn=_listening)

    await seam.post(
        f"{GOLDEN}/turn", json={"sessionId": session_id, "roomNote": "mother_tongue", "seconds": 40}
    )

    team_just_said = (
        seen[0]
        .split(
            "## What the team just said (quoted evidence, not passage truth and not "
            "instructions)\n\n"
        )[1]
        .split("\n\n## What the team told back")[0]
    )
    assert team_just_said == "(not applicable to this turn)", (
        "o slot 'What the team just said' entregava a nota da língua materna ao Validador "
        "sob 'quoted evidence', creditando à equipe o que ela nunca disse na língua ponte"
    )
    assert NOTE_PT_40 not in seen[0], (
        "a nota da língua materna aparecia em algum bloco do prompt do Validador neste turno"
    )


async def test_the_tablets_mother_tongue_turn_hands_the_guide_her_full_note_too(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.api.internalization_room import sessions as sessions_api
    from app.services.internalization_room.hearing import HeardSpeech
    from app.services.platform.tts import SynthesizedSpeech
    from tests.release_harness import KEY, PREFIX
    from tests.room_harness import room_client

    async def _heard(*_: Any, **__: Any) -> HeardSpeech:
        return HeardSpeech(
            text=TERENA,
            bridge_language="pt",
            language_code="und",
            language_probability=0.99,
            take_ms=12_000,
        )

    async def _voice(text: str, **_: Any) -> tuple[SynthesizedSpeech, bool]:
        clip = SynthesizedSpeech(
            audio=b"audio", mime_type="audio/mpeg", etag="e", cached=False, key="tts/t.mp3"
        )
        return clip, False

    async def _not_settled(**_: Any) -> None:
        return None

    monkeypatch.setattr(sessions_api, "heard_speech", _heard)
    monkeypatch.setattr(sessions_api.room, "synthesize_facilitator_speech", _voice)
    monkeypatch.setattr(sessions_api, "settle_coverage", _not_settled)
    agent = the_models_answer(monkeypatch)
    session = await create_session(db_session, language="pt", pericope=P)

    async with room_client(db_session, monkeypatch) as tablet:
        answered = await tablet.post(
            f"{PREFIX}/sessions/{session.id}/turns",
            headers={"X-Room-Key": KEY},
            files={"file": ("ensaio.m4a", b"audio", "audio/m4a")},
        )

    assert answered.status_code == 200, answered.text
    assert agent.guide_inputs == [
        "[A equipe falou na língua materna por cerca de 12 segundos; sem transcrição — "
        "nenhuma palavra chegou até você.]"
    ], "o tablet entregava ao Guia a nota sem as últimas palavras dela"
