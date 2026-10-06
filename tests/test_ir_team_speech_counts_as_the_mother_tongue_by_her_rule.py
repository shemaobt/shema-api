"""The team's take counts as the mother tongue exactly as Marcia's `decideTeamUtterance` decides.

Three conditions and nothing else: another language heard, the session's language heard under
the mother-tongue floor, or a take with no words lasting twenty seconds or more. Every other
take reaches the Guide as the team's words, and a short take with no words draws the D line.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import sessions as sessions_api
from app.core.config import Settings, get_settings
from app.core.exceptions import ValidationError
from app.db.models.internalization_room import IRSession
from app.services import internalization_room as room
from app.services.internalization_room import hearing
from app.services.internalization_room.live_turn import run_comprehension_turn
from app.services.internalization_room.sessions import (
    append_exchange,
    comprehension_of,
    create_session,
    save_comprehension,
)
from app.services.platform.tts import SynthesizedSpeech
from app.services.translation_helper.transcribe_audio import TranscriptionResult
from tests.release_harness import KEY, PREFIX
from tests.room_harness import room_client
from tests.text_seam_harness import (
    BEARER,
    GOLDEN,
    RUNNER_KEY,
    ScriptedAgent,
    the_app,
    the_models_answer,
)
from tests.turn_harness import GUIDE, VALIDATOR, P, settings, the_room_agent_is

PORTUGUESE = "Noemi voltou para Belém com Rute no tempo da colheita"
TERENA_AS_SPANISH = "koeti yoko vitukeovo enepone itukovo"
INVITATION = "Agora ensaiem esta cena juntos na língua de vocês; quando terminarem, digam: pronto."
CONVERSATION = "Contem mais sobre o que aconteceu com essas pessoas."


def _note(seconds: int) -> str:
    return (
        f"[A equipe falou na língua materna por cerca de {seconds} segundos; sem transcrição — "
        "nenhuma palavra chegou até você.]"
    )


Transcriber = Callable[..., Awaitable[TranscriptionResult]]


def _the_transcriber_hears(
    text: str,
    language_code: str | None,
    language_probability: float | None,
    transcript_confidence: float | None = None,
) -> Transcriber:
    async def _detailed(*_: Any, **__: Any) -> TranscriptionResult:
        return TranscriptionResult(
            text=text,
            language_code=language_code,
            language_probability=language_probability,
            transcript_confidence=transcript_confidence,
        )

    return _detailed


async def _the_transcriber_hears_nothing(*_: Any, **__: Any) -> TranscriptionResult:
    raise ValidationError("Transcription returned empty text")


def _the_take_lasts(ms: int | None) -> Callable[[bytes], Awaitable[int | None]]:
    async def _measure(_: bytes) -> int | None:
        return ms

    return _measure


async def _voice(text: str, **_: Any) -> tuple[SynthesizedSpeech, bool]:
    clip = SynthesizedSpeech(
        audio=b"audio", mime_type="audio/mpeg", etag="e", cached=False, key="tts/t.mp3"
    )
    return clip, False


async def _not_settled(**_: Any) -> None:
    return None


@pytest.fixture
async def tablet(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[httpx.AsyncClient]:
    monkeypatch.setattr(sessions_api.room, "synthesize_facilitator_speech", _voice)
    monkeypatch.setattr(sessions_api, "settle_coverage", _not_settled)
    async with room_client(db_session, monkeypatch) as client:
        yield client


@pytest.fixture
def guide(monkeypatch: pytest.MonkeyPatch) -> ScriptedAgent:
    return the_models_answer(monkeypatch)


async def _an_open_session(
    db_session: AsyncSession, tablet: httpx.AsyncClient, guide: ScriptedAgent
) -> IRSession:
    session = await create_session(db_session, language="pt", pericope=P)
    opened = await tablet.post(f"{PREFIX}/sessions/{session.id}/turns", headers={"X-Room-Key": KEY})
    assert opened.status_code == 200, opened.text
    guide.guide_inputs.clear()
    return session


async def _the_team_sends_a_take(
    tablet: httpx.AsyncClient,
    session: IRSession,
    monkeypatch: pytest.MonkeyPatch,
    *,
    transcriber: Transcriber,
    take_ms: int | None,
) -> dict[str, Any]:
    monkeypatch.setattr(hearing, "transcribe_audio_detailed", transcriber)
    monkeypatch.setattr(hearing, "measure_ms", _the_take_lasts(take_ms))
    answered = await tablet.post(
        f"{PREFIX}/sessions/{session.id}/turns",
        headers={"X-Room-Key": KEY},
        files={"file": ("ensaio.m4a", b"audio", "audio/m4a")},
    )
    assert answered.status_code == 200, answered.text
    reply: dict[str, Any] = answered.json()
    return reply


async def _the_turns_record(db_session: AsyncSession, session_id: str) -> dict[str, Any]:
    db_session.expire_all()
    stored = await room.get_session(db_session, session_id)
    guide_entry: dict[str, Any] = stored.messages[-1]
    return {
        key: guide_entry.get(key, "absent")
        for key in ("language", "language_probability", "mother_tongue", "take_ms")
    }


async def test_a_terena_take_the_transcriber_labels_as_spanish_at_0_7_reaches_the_guide_as_the_mother_tongue_note(  # noqa: E501
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_session(db_session, tablet, guide)

    await _the_team_sends_a_take(
        tablet,
        session,
        monkeypatch,
        transcriber=_the_transcriber_hears(TERENA_AS_SPANISH, "spa", 0.7),
        take_ms=40_000,
    )

    assert guide.guide_inputs == [_note(40)], (
        "o Guia recebia o espanhol inventado pelo reconhecedor como palavras da equipe"
    )


async def test_one_word_heard_as_another_language_at_a_low_probability_is_still_the_mother_tongue(
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_session(db_session, tablet, guide)

    await _the_team_sends_a_take(
        tablet,
        session,
        monkeypatch,
        transcriber=_the_transcriber_hears("pronto", "spa", 0.12),
        take_ms=3_000,
    )

    assert guide.guide_inputs == [_note(3)]


async def test_a_take_heard_as_portuguese_at_0_30_in_a_portuguese_session_reaches_the_guide_as_the_mother_tongue_note(  # noqa: E501
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_session(db_session, tablet, guide)

    await _the_team_sends_a_take(
        tablet,
        session,
        monkeypatch,
        transcriber=_the_transcriber_hears(TERENA_AS_SPANISH, "pt", 0.30),
        take_ms=15_000,
    )

    assert guide.guide_inputs == [_note(15)]


async def test_a_take_heard_as_portuguese_exactly_at_the_floor_reaches_the_guide_as_words(
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_session(db_session, tablet, guide)

    await _the_team_sends_a_take(
        tablet,
        session,
        monkeypatch,
        transcriber=_the_transcriber_hears(PORTUGUESE, "pt", 0.35),
        take_ms=15_000,
    )

    assert guide.guide_inputs == [PORTUGUESE]


async def test_clear_portuguese_at_0_9_reaches_the_guide_as_the_teams_words_and_is_never_answered_with_a_d_line(  # noqa: E501
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_session(db_session, tablet, guide)

    reply = await _the_team_sends_a_take(
        tablet,
        session,
        monkeypatch,
        transcriber=_the_transcriber_hears(PORTUGUESE, "pt", 0.9),
        take_ms=12_000,
    )

    assert guide.guide_inputs == [PORTUGUESE]
    assert reply["fixed_line"] == ""


async def test_portuguese_the_transcriber_is_unsure_of_word_by_word_still_reaches_the_guide_as_words(  # noqa: E501
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_session(db_session, tablet, guide)

    reply = await _the_team_sends_a_take(
        tablet,
        session,
        monkeypatch,
        transcriber=_the_transcriber_hears(PORTUGUESE, "pt", 0.9, transcript_confidence=0.2),
        take_ms=12_000,
    )

    assert guide.guide_inputs == [PORTUGUESE], (
        "português claro com log-probabilidades baixas por palavra virava pedido para repetir"
    )
    assert reply["fixed_line"] == ""


async def test_words_with_no_detected_language_reach_the_guide_as_words(
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_session(db_session, tablet, guide)

    await _the_team_sends_a_take(
        tablet,
        session,
        monkeypatch,
        transcriber=_the_transcriber_hears(PORTUGUESE, None, None),
        take_ms=12_000,
    )

    assert guide.guide_inputs == [PORTUGUESE]


async def test_a_take_with_no_words_lasting_25_seconds_reaches_the_guide_as_the_mother_tongue_note_saying_25_seconds(  # noqa: E501
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_session(db_session, tablet, guide)

    reply = await _the_team_sends_a_take(
        tablet,
        session,
        monkeypatch,
        transcriber=_the_transcriber_hears_nothing,
        take_ms=25_000,
    )

    assert guide.guide_inputs == [_note(25)], (
        "dois minutos de ensaio sem palavras eram respondidos com o pedido para repetir"
    )
    assert reply["fixed_line"] == ""


async def test_a_take_whose_only_content_is_pause_for_30_seconds_reaches_the_guide_as_the_mother_tongue_note_saying_30_seconds(  # noqa: E501
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_session(db_session, tablet, guide)

    await _the_team_sends_a_take(
        tablet,
        session,
        monkeypatch,
        transcriber=_the_transcriber_hears("[pause]", "pt", 0.9),
        take_ms=30_000,
    )

    assert guide.guide_inputs == [_note(30)]


async def test_a_take_with_no_words_lasting_8_seconds_is_answered_with_d_1_and_the_guide_is_not_called(  # noqa: E501
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_session(db_session, tablet, guide)

    reply = await _the_team_sends_a_take(
        tablet,
        session,
        monkeypatch,
        transcriber=_the_transcriber_hears_nothing,
        take_ms=8_000,
    )

    assert reply["fixed_line"] == "D0"
    assert guide.guide_inputs == []


async def test_a_take_with_no_words_whose_length_cannot_be_measured_is_answered_with_d_1(
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_session(db_session, tablet, guide)

    reply = await _the_team_sends_a_take(
        tablet,
        session,
        monkeypatch,
        transcriber=_the_transcriber_hears_nothing,
        take_ms=None,
    )

    assert reply["fixed_line"] == "D0"
    assert guide.guide_inputs == []


async def test_a_take_with_no_words_lasting_exactly_20_seconds_is_the_mother_tongue(
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_session(db_session, tablet, guide)

    reply = await _the_team_sends_a_take(
        tablet,
        session,
        monkeypatch,
        transcriber=_the_transcriber_hears_nothing,
        take_ms=20_000,
    )

    assert guide.guide_inputs == [_note(20)]
    assert reply["fixed_line"] == ""


async def test_the_floor_raised_to_0_40_between_sessions_is_the_floor_the_next_sessions_turns_use(
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unsure_portuguese = _the_transcriber_hears(PORTUGUESE, "pt", 0.38)
    before = await _an_open_session(db_session, tablet, guide)
    await _the_team_sends_a_take(
        tablet, before, monkeypatch, transcriber=unsure_portuguese, take_ms=12_000
    )
    assert guide.guide_inputs == [PORTUGUESE]

    monkeypatch.setattr(get_settings(), "internalization_room_mother_tongue_floor", 0.40)
    after = await _an_open_session(db_session, tablet, guide)
    await _the_team_sends_a_take(
        tablet, after, monkeypatch, transcriber=unsure_portuguese, take_ms=12_000
    )

    assert guide.guide_inputs == [_note(12)], (
        "o piso subiu na configuração e a sessão seguinte ainda ouvia pelo piso antigo"
    )


def test_the_floor_is_read_from_the_environment_and_defaults_to_0_35(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("INTERNALIZATION_ROOM_MOTHER_TONGUE_FLOOR", raising=False)
    untouched = Settings(database_url="sqlite+aiosqlite:///./test.db", _env_file=None)
    monkeypatch.setenv("INTERNALIZATION_ROOM_MOTHER_TONGUE_FLOOR", "0.4")
    raised = Settings(database_url="sqlite+aiosqlite:///./test.db", _env_file=None)

    assert untouched.internalization_room_mother_tongue_floor == 0.35
    assert raised.internalization_room_mother_tongue_floor == 0.4


def test_the_production_deploy_names_the_mother_tongue_floor_and_it_is_the_default() -> None:
    import yaml

    path = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "deploy.yml"
    steps = yaml.safe_load(path.read_text(encoding="utf-8"))["jobs"]["deploy"]["steps"]
    deploy_step = next(step for step in steps if step["name"] == "Deploy Backend")
    token = next(t for t in deploy_step["run"].split() if t.startswith("--update-env-vars="))
    delimited = token.removeprefix("--update-env-vars=").strip('"')
    pairs = dict(pair.split("=", 1) for pair in delimited.removeprefix("^|^").split("|"))

    default = Settings.model_fields["internalization_room_mother_tongue_floor"].default
    assert float(pairs["INTERNALIZATION_ROOM_MOTHER_TONGUE_FLOOR"]) == default


async def test_after_a_turn_in_words_the_stored_record_shows_the_language_its_probability_the_mother_tongue_decision_and_the_takes_length(  # noqa: E501
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_session(db_session, tablet, guide)

    await _the_team_sends_a_take(
        tablet,
        session,
        monkeypatch,
        transcriber=_the_transcriber_hears(PORTUGUESE, "pt", 0.9),
        take_ms=12_000,
    )

    assert await _the_turns_record(db_session, session.id) == {
        "language": "pt",
        "language_probability": 0.9,
        "mother_tongue": False,
        "take_ms": 12_000,
    }
    opening = (await room.get_session(db_session, session.id)).messages[0]
    assert "mother_tongue" not in opening, "a abertura, que ninguém ouviu, ganhava um registro"


async def test_after_a_mother_tongue_turn_the_stored_record_shows_the_language_its_probability_the_decision_and_the_takes_length(  # noqa: E501
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_session(db_session, tablet, guide)

    await _the_team_sends_a_take(
        tablet,
        session,
        monkeypatch,
        transcriber=_the_transcriber_hears(TERENA_AS_SPANISH, "spa", 0.7),
        take_ms=40_000,
    )

    assert await _the_turns_record(db_session, session.id) == {
        "language": "spa",
        "language_probability": 0.7,
        "mother_tongue": True,
        "take_ms": 40_000,
    }


async def test_after_a_turn_answered_with_d_1_the_stored_record_shows_no_language_the_decision_false_and_the_takes_length(  # noqa: E501
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_session(db_session, tablet, guide)

    await _the_team_sends_a_take(
        tablet,
        session,
        monkeypatch,
        transcriber=_the_transcriber_hears_nothing,
        take_ms=8_000,
    )

    assert await _the_turns_record(db_session, session.id) == {
        "language": None,
        "language_probability": None,
        "mother_tongue": False,
        "take_ms": 8_000,
    }


@pytest.fixture
async def seam(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[httpx.AsyncClient]:
    monkeypatch.setattr(
        get_settings(), "internalization_room_runner_key", RUNNER_KEY, raising=False
    )
    transport = ASGITransport(app=the_app(db_session))
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", headers=BEARER
    ) as client:
        yield client


async def test_a_mother_tongue_note_from_the_golden_door_still_reaches_the_guide_as_the_note_and_its_record_says_mother_tongue(  # noqa: E501
    seam: httpx.AsyncClient, db_session: AsyncSession, guide: ScriptedAgent
) -> None:
    created = await seam.post(
        f"{GOLDEN}/session", json={"pericopeId": "P01", "language": "Brazilian Portuguese"}
    )
    session_id = created.json()["sessionId"]
    await seam.post(f"{GOLDEN}/turn", json={"sessionId": session_id, "roomNote": "session_start"})
    guide.guide_inputs.clear()

    answered = await seam.post(
        f"{GOLDEN}/turn", json={"sessionId": session_id, "roomNote": "mother_tongue", "seconds": 40}
    )

    assert answered.status_code == 200, answered.text
    assert guide.guide_inputs == [_note(40)]
    assert (await _the_turns_record(db_session, session_id))["mother_tongue"] is True


async def test_a_low_word_confidence_portuguese_answer_is_handed_to_the_coverage_classifier(
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_session(db_session, tablet, guide)

    reply = await _the_team_sends_a_take(
        tablet,
        session,
        monkeypatch,
        transcriber=_the_transcriber_hears(PORTUGUESE, "pt", 0.9, transcript_confidence=0.2),
        take_ms=12_000,
    )

    assert reply["classification_pending"] is True, (
        "uma resposta em português com confiança baixa por palavra nunca chegava ao classificador"
    )


class _ScriptedGuide:
    """A Guide that says the lines the case wrote, one per turn, and a Validator that passes."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    async def __call__(self, *, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return self.lines.pop(0)


async def _a_heard_turn(
    db_session: AsyncSession,
    session: IRSession,
    scripted: _ScriptedGuide,
    monkeypatch: pytest.MonkeyPatch,
    *,
    transcriber: Transcriber,
    line: str,
) -> None:
    monkeypatch.setattr(hearing, "transcribe_audio_detailed", transcriber)
    monkeypatch.setattr(hearing, "measure_ms", _the_take_lasts(4_000))
    speech = await hearing.heard_speech(b"audio", language=session.language, settings=settings())
    scripted.lines.append(line)
    turn = await run_comprehension_turn(
        db_session,
        session,
        speech=speech,
        opening=False,
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        settings=settings(),
    )
    await save_comprehension(db_session, session, turn.state)
    await append_exchange(
        db_session, session, team_utterance=speech.text, guide_response=turn.outcome.speech
    )


async def test_a_teams_report_of_a_finished_rehearsal_heard_with_low_word_confidence_credits_the_scene_the_guide_invited(  # noqa: E501
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    scripted = _ScriptedGuide()
    the_room_agent_is(monkeypatch, turn=scripted)
    session = await create_session(db_session, language="pt", pericope=P)
    session = await append_exchange(
        db_session, session, team_utterance="", guide_response="abertura"
    )
    await _a_heard_turn(
        db_session,
        session,
        scripted,
        monkeypatch,
        transcriber=_the_transcriber_hears("uma mulher volta para o seu povo", "pt", 0.9),
        line=INVITATION,
    )

    await _a_heard_turn(
        db_session,
        session,
        scripted,
        monkeypatch,
        transcriber=_the_transcriber_hears(
            "pronto, terminamos", "pt", 0.9, transcript_confidence=0.1
        ),
        line=CONVERSATION,
    )

    assert comprehension_of(session).practiced_scene_ids == ["S1"], (
        "o relato de ensaio terminado ouvido com confiança baixa por palavra não creditava a cena"
    )
