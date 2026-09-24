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
from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.canon.book_material import build_book_material
from app.services.internalization_room.hearing import HeardSpeech, heard_speech
from app.services.internalization_room.languages import LANGUAGE_NAMES
from app.services.internalization_room.live_turn import run_comprehension_turn
from app.services.internalization_room.run_turn import TurnOutcome, run_panorama_turn
from app.services.internalization_room.sessions import create_session
from app.services.internalization_room.validated_turn import TEAM_JUST_SAID
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


async def _heard(audio: bytes) -> HeardSpeech:
    return await heard_speech(
        audio,
        filename="take.wav",
        language="pt",
        settings=Settings(database_url="sqlite+aiosqlite:///./test.db", elevenlabs_api_key="k"),
    )


async def _the_room_hears(db_session: AsyncSession, audio: bytes) -> TurnOutcome:
    session = await create_session(db_session, language="pt", pericope=P)
    speech = await _heard(audio)
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


P06_NOTE = (
    "[A equipe falou na língua materna por cerca de 116 segundos; sem transcrição — nenhuma "
    "palavra chegou até você.]"
)
P06_SCRIBE = {"text": "", "language_code": "eng", "language_probability": 0.65}


async def test_two_minutes_of_rehearsal_scribe_returned_no_words_for_reach_the_guide_as_her_note(
    db_session: AsyncSession, agent: FakeAgent, monkeypatch: pytest.MonkeyPatch
) -> None:
    _scribe_answers(monkeypatch, 200, P06_SCRIBE)

    outcome = await _the_room_hears(db_session, _take(116))

    assert agent.guide_inputs == [P06_NOTE], (
        "a equipe que ensaiou dois minutos na língua dela ouvia 'podem repetir?' (P06, turno 21)"
    )
    assert outcome.fixed_line == ""
    assert outcome.room_note == P06_NOTE


async def test_a_short_take_scribe_returned_no_words_for_is_line_d_with_no_model_called(
    db_session: AsyncSession, agent: FakeAgent, monkeypatch: pytest.MonkeyPatch
) -> None:
    _scribe_answers(monkeypatch, 200, P06_SCRIBE)

    outcome = await _the_room_hears(db_session, _take(6))

    assert outcome.fixed_line == "D0"
    assert agent.calls == []


async def test_a_long_take_scribe_heard_only_as_silence_is_her_note(
    db_session: AsyncSession, agent: FakeAgent, monkeypatch: pytest.MonkeyPatch
) -> None:
    _scribe_answers(
        monkeypatch,
        200,
        {"text": "[silence]", "language_code": "por", "language_probability": 0.9},
    )

    outcome = await _the_room_hears(db_session, _take(25))

    assert outcome.room_note == (
        "[A equipe falou na língua materna por cerca de 25 segundos; sem transcrição — nenhuma "
        "palavra chegou até você.]"
    ), "uma tomada longa que o Scribe só descreveu como silêncio virava a linha D"


async def test_a_long_take_scribe_refused_is_line_d_never_the_mother_tongue(
    db_session: AsyncSession, agent: FakeAgent, monkeypatch: pytest.MonkeyPatch
) -> None:
    _scribe_answers(monkeypatch, 422, {"detail": "invalid audio"})

    outcome = await _the_room_hears(db_session, _take(30))

    assert outcome.fixed_line == "D0"
    assert agent.calls == []


async def test_a_wordless_take_nobody_could_measure_is_line_d(
    db_session: AsyncSession, agent: FakeAgent, monkeypatch: pytest.MonkeyPatch
) -> None:
    _scribe_answers(monkeypatch, 200, P06_SCRIBE)

    outcome = await _the_room_hears(db_session, b"isto nao e audio nenhum" * 4000)

    assert outcome.fixed_line == "D0"
    assert agent.calls == []


async def test_only_a_wordless_take_is_measured_never_one_in_the_sessions_language(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services.internalization_room import hearing

    the_agent_answers(
        monkeypatch,
        FakeAgent(verdicts=[{"verdict": "pass", "issues": []}] * 2, drafts=[WELCOME] * 2),
    )
    measured: list[int] = []
    real_measure = hearing.measure_ms

    async def _measure(audio: bytes) -> int | None:
        measured.append(len(audio))
        return await real_measure(audio)

    monkeypatch.setattr(hearing, "measure_ms", _measure)
    _scribe_answers(
        monkeypatch,
        200,
        {"text": "Entendemos tudo.", "language_code": "por", "language_probability": 0.9},
    )
    await _the_room_hears(db_session, _take(6))
    _scribe_answers(monkeypatch, 200, P06_SCRIBE)
    await _the_room_hears(db_session, _take(21))

    assert measured == [len(_take(21))], (
        "o ffprobe rodava em toda tomada, ou nunca na que chegou sem palavras"
    )


async def test_a_telling_back_scribe_returned_no_words_for_is_still_an_empty_telling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.internalization_room.hearing import heard

    _scribe_answers(monkeypatch, 200, P06_SCRIBE)

    told = await heard(
        _take(116),
        filename="take.wav",
        settings=Settings(database_url="sqlite+aiosqlite:///./test.db", elevenlabs_api_key="k"),
    )

    assert told == "", "o 200 vazio escapava do heard() da retro e virava um 400 para o app"


class _ValidatorWatched(FakeAgent):
    def __init__(self) -> None:
        super().__init__(verdicts=[{"verdict": "pass", "issues": []}], drafts=[WELCOME])
        self.validator_systems: list[str] = []

    async def __call__(self, *, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        if "corrected_response" in system_prompt:
            self.validator_systems.append(system_prompt)
        return await super().__call__(
            system_prompt=system_prompt, user_content=user_content, **kwargs
        )


async def _the_panorama_hears(audio: bytes) -> TurnOutcome:
    speech = await _heard(audio)
    return await run_panorama_turn(
        transcript=speech.text,
        mother_tongue=speech.mother_tongue,
        take_ms=speech.take_ms,
        messages=[{"role": "guide", "text": "Vamos conhecer o livro de Rute."}],
        panorama_prompt=default_prompt(IRPromptKey.BOOK_PANORAMA)["prompt"],
        validator_prompt=VALIDATOR,
        book="Ruth",
        book_material=build_book_material("Ruth"),
        session_language=LANGUAGE_NAMES["pt"],
        language_code="pt",
        settings=settings(),
    )


async def test_a_panorama_take_in_another_language_hands_guide_and_validator_her_note(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agent = the_agent_answers(monkeypatch, _ValidatorWatched())
    _scribe_answers(
        monkeypatch,
        200,
        {"text": "Kalivono itukovo", "language_code": "grn", "language_probability": 0.90},
    )

    outcome = await _the_panorama_hears(_take(6))

    assert agent.guide_inputs == [NOTE_PT_6], (
        "o panorama entregava ao Guia as palavras que o reconhecedor inventou"
    )
    assert TEAM_JUST_SAID + NOTE_PT_6 in agent.validator_systems[0]
    assert "Kalivono" not in agent.validator_systems[0]
    assert outcome.transcript == ""
    assert outcome.room_note == NOTE_PT_6


async def test_two_minutes_the_panorama_heard_no_word_of_are_her_note_not_line_d(
    agent: FakeAgent, monkeypatch: pytest.MonkeyPatch
) -> None:
    _scribe_answers(monkeypatch, 200, P06_SCRIBE)

    outcome = await _the_panorama_hears(_take(116))

    assert agent.guide_inputs == [P06_NOTE], "o panorama respondia 'podem repetir?' ao ensaio"
    assert outcome.fixed_line == ""
    assert outcome.room_note == P06_NOTE
