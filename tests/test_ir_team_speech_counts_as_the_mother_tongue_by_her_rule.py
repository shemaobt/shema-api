"""The team's take counts as the mother tongue exactly as Marcia's `decideTeamUtterance` decides.

Three conditions and nothing else: another language heard, the session's language heard under
the mother-tongue floor, or a take with no words lasting twenty seconds or more. Every other
take reaches the Guide as the team's words, and a short take with no words draws the D line.
A take the recognizer refused is a miss, never the mother tongue, and a length the probe
cannot give in time is an unknown length, never an error.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pydantic
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
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
from tests.deploy_harness import deploy_env_vars
from tests.hearing_harness import (
    a_golden_session,
    nothing_settles,
    the_probe_fails,
    the_probe_never_answers,
    the_take_lasts,
    the_transcriber_hears,
    the_transcriber_hears_no_words,
    the_transcriber_refuses,
)
from tests.release_harness import KEY, PREFIX
from tests.room_harness import room_client, the_room_speaks
from tests.text_seam_harness import GOLDEN, RUNNER_KEY, ScriptedAgent, the_models_answer
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


@pytest.fixture
async def seam(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[httpx.AsyncClient]:
    async with room_client(db_session, monkeypatch, runner_key=RUNNER_KEY) as client:
        yield client


async def _an_open_session(
    db_session: AsyncSession, tablet: httpx.AsyncClient, guide: ScriptedAgent
) -> IRSession:
    session = await create_session(db_session, language="pt", pericope=P)
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
    the_transcriber_hears(monkeypatch, TERENA_AS_SPANISH, "spa", 0.7)
    the_take_lasts(monkeypatch, 40_000)

    await _the_team_sends_a_take(tablet, session)

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
    the_transcriber_hears(monkeypatch, "pronto", "spa", 0.12)
    the_take_lasts(monkeypatch, 3_000)

    await _the_team_sends_a_take(tablet, session)

    assert guide.guide_inputs == [_note(3)]


async def test_a_take_heard_as_portuguese_at_0_30_in_a_portuguese_session_reaches_the_guide_as_the_mother_tongue_note(  # noqa: E501
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_session(db_session, tablet, guide)
    the_transcriber_hears(monkeypatch, TERENA_AS_SPANISH, "pt", 0.30)
    the_take_lasts(monkeypatch, 15_000)

    await _the_team_sends_a_take(tablet, session)

    assert guide.guide_inputs == [_note(15)]


async def test_a_take_heard_as_portuguese_exactly_at_the_floor_reaches_the_guide_as_words(
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_session(db_session, tablet, guide)
    the_transcriber_hears(monkeypatch, PORTUGUESE, "pt", 0.35)
    the_take_lasts(monkeypatch, 15_000)

    await _the_team_sends_a_take(tablet, session)

    assert guide.guide_inputs == [PORTUGUESE]


async def test_clear_portuguese_at_0_9_reaches_the_guide_as_the_teams_words_and_is_never_answered_with_a_d_line(  # noqa: E501
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_session(db_session, tablet, guide)
    the_transcriber_hears(monkeypatch, PORTUGUESE, "pt", 0.9)
    the_take_lasts(monkeypatch, 12_000)

    reply = await _the_team_sends_a_take(tablet, session)

    assert guide.guide_inputs == [PORTUGUESE]
    assert reply["fixed_line"] == ""


async def test_portuguese_the_transcriber_is_unsure_of_word_by_word_still_reaches_the_guide_as_words(  # noqa: E501
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_session(db_session, tablet, guide)
    the_transcriber_hears(monkeypatch, PORTUGUESE, "pt", 0.9, transcript_confidence=0.2)
    the_take_lasts(monkeypatch, 12_000)

    reply = await _the_team_sends_a_take(tablet, session)

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
    the_transcriber_hears(monkeypatch, PORTUGUESE, None, None)
    the_take_lasts(monkeypatch, 12_000)

    await _the_team_sends_a_take(tablet, session)

    assert guide.guide_inputs == [PORTUGUESE]


async def test_portuguese_heard_with_a_region_written_with_an_underscore_reaches_the_guide_as_words(
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_session(db_session, tablet, guide)
    the_transcriber_hears(monkeypatch, PORTUGUESE, "pt_BR", 0.9)
    the_take_lasts(monkeypatch, 12_000)

    await _the_team_sends_a_take(tablet, session)

    assert guide.guide_inputs == [PORTUGUESE], (
        "pt_BR não era lido como a língua da sessão e o português virava nota de língua materna"
    )


async def test_a_take_with_no_words_lasting_25_seconds_reaches_the_guide_as_the_mother_tongue_note_saying_25_seconds(  # noqa: E501
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_session(db_session, tablet, guide)
    the_transcriber_hears_no_words(monkeypatch)
    the_take_lasts(monkeypatch, 25_000)

    reply = await _the_team_sends_a_take(tablet, session)

    assert guide.guide_inputs == [_note(25)], (
        "dois minutos de ensaio sem palavras eram respondidos com o pedido para repetir"
    )
    assert reply["fixed_line"] == ""


async def test_a_take_with_no_words_heard_as_english_at_0_65_keeps_that_language_in_its_record(
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_session(db_session, tablet, guide)
    the_transcriber_hears_no_words(monkeypatch, "eng", 0.65)
    the_take_lasts(monkeypatch, 25_000)

    await _the_team_sends_a_take(tablet, session)

    assert guide.guide_inputs == [_note(25)]
    assert await _the_turns_record(db_session, session.id) == {
        "language": "eng",
        "language_probability": 0.65,
        "mother_tongue": True,
        "take_ms": 25_000,
    }, "o registro de um take sem palavras perdia a língua que o reconhecedor ouviu"


async def test_the_recognizers_answer_with_no_words_still_names_the_language_it_heard() -> None:
    from app.core.exceptions import NoWordsHeard
    from app.services.translation_helper.transcribe_audio import transcribe_audio_detailed

    def elevenlabs(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"text": "", "language_code": "eng", "language_probability": 0.65}
        )

    keyed = Settings(
        database_url="sqlite+aiosqlite:///./test.db", elevenlabs_api_key="key", _env_file=None
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(elevenlabs)) as client:
        with pytest.raises(NoWordsHeard) as heard:
            await transcribe_audio_detailed(b"audio", settings=keyed, client=client)

    assert (heard.value.language_code, heard.value.language_probability) == ("eng", 0.65)


async def test_a_take_the_recognizer_refused_is_answered_with_d_1_and_never_counts_as_the_mother_tongue(  # noqa: E501
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_session(db_session, tablet, guide)
    the_transcriber_refuses(monkeypatch)
    the_take_lasts(monkeypatch, 25_000)

    reply = await _the_team_sends_a_take(tablet, session)

    assert reply["fixed_line"] == "D0", (
        "um STT mal configurado recusava todo take e cada take longo virava língua materna"
    )
    assert guide.guide_inputs == []
    assert await _the_turns_record(db_session, session.id) == {
        "language": None,
        "language_probability": None,
        "mother_tongue": False,
        "take_ms": None,
    }


async def test_a_take_whose_only_content_is_pause_for_30_seconds_reaches_the_guide_as_the_mother_tongue_note_saying_30_seconds(  # noqa: E501
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_session(db_session, tablet, guide)
    the_transcriber_hears(monkeypatch, "[pause]", "pt", 0.9)
    the_take_lasts(monkeypatch, 30_000)

    await _the_team_sends_a_take(tablet, session)

    assert guide.guide_inputs == [_note(30)]


async def test_a_take_with_no_words_lasting_8_seconds_is_answered_with_d_1_and_the_guide_is_not_called(  # noqa: E501
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_session(db_session, tablet, guide)
    the_transcriber_hears_no_words(monkeypatch)
    the_take_lasts(monkeypatch, 8_000)

    reply = await _the_team_sends_a_take(tablet, session)

    assert reply["fixed_line"] == "D0"
    assert guide.guide_inputs == []


async def test_a_take_with_no_words_whose_length_cannot_be_measured_is_answered_with_d_1(
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_session(db_session, tablet, guide)
    the_transcriber_hears_no_words(monkeypatch)
    the_take_lasts(monkeypatch, None)

    reply = await _the_team_sends_a_take(tablet, session)

    assert reply["fixed_line"] == "D0"
    assert guide.guide_inputs == []


async def test_a_take_with_no_words_whose_probe_never_answers_is_answered_with_d_1(
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(hearing, "MEASURING_BOUND_S", 0.05)
    session = await _an_open_session(db_session, tablet, guide)
    the_transcriber_hears_no_words(monkeypatch)
    the_probe_never_answers(monkeypatch)

    try:
        reply = await asyncio.wait_for(_the_team_sends_a_take(tablet, session), timeout=5)
    except TimeoutError:
        pytest.fail("um ffprobe travado segurava o turno até o teto de 300 s")

    assert reply["fixed_line"] == "D0"
    assert guide.guide_inputs == []


async def test_a_probe_that_never_answers_is_stopped_once_the_bound_has_passed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from app.services.platform import audio_duration

    pid_file = tmp_path / "probe.pid"
    hung_probe = tmp_path / "ffprobe"
    hung_probe.write_text(f"#!/bin/sh\necho $$ > {pid_file}\nexec sleep 60\n")
    hung_probe.chmod(0o755)
    monkeypatch.setattr(audio_duration, "PROBE", str(hung_probe))
    bound = 3600.0
    monkeypatch.setattr(hearing, "MEASURING_BOUND_S", bound)
    the_transcriber_hears_no_words(monkeypatch)
    hearing_the_take = asyncio.create_task(
        hearing.heard_speech(b"audio", language="pt", settings=settings())
    )

    async with asyncio.timeout(30):
        while not hearing_the_take.done() and (
            not pid_file.exists() or not pid_file.read_text().endswith("\n")
        ):
            await asyncio.sleep(0.01)
    assert not hearing_the_take.done(), (
        "the take ended before the probe started: "
        f"{hearing_the_take.exception() or hearing_the_take.result()!r}"
    )
    loop = asyncio.get_running_loop()
    loop_time = loop.time
    monkeypatch.setattr(loop, "time", lambda: loop_time() + bound + 1)
    try:
        done, _ = await asyncio.wait({hearing_the_take}, timeout=10)
        assert done, "um ffprobe travado seguia segurando a medida depois do teto"
    finally:
        hearing_the_take.cancel()
        await asyncio.wait({hearing_the_take})

    assert hearing_the_take.result().take_ms is None
    with pytest.raises(ProcessLookupError):
        os.kill(int(pid_file.read_text()), 0)


async def test_words_whose_take_the_probe_fails_on_still_reach_the_guide_as_words(
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_session(db_session, tablet, guide)
    the_transcriber_hears(monkeypatch, PORTUGUESE, "pt", 0.9)
    the_probe_fails(monkeypatch)

    await _the_team_sends_a_take(tablet, session)

    assert guide.guide_inputs == [PORTUGUESE], "uma falha do ffprobe virava erro 500 no turno"


async def test_a_take_with_no_words_lasting_exactly_20_seconds_is_the_mother_tongue(
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_session(db_session, tablet, guide)
    the_transcriber_hears_no_words(monkeypatch)
    the_take_lasts(monkeypatch, 20_000)

    reply = await _the_team_sends_a_take(tablet, session)

    assert guide.guide_inputs == [_note(20)]
    assert reply["fixed_line"] == ""


async def test_the_floor_raised_to_0_40_between_sessions_is_the_floor_the_next_sessions_turns_use(
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    the_transcriber_hears(monkeypatch, PORTUGUESE, "pt", 0.38)
    the_take_lasts(monkeypatch, 12_000)
    before = await _an_open_session(db_session, tablet, guide)
    await _the_team_sends_a_take(tablet, before)
    assert guide.guide_inputs == [PORTUGUESE]

    monkeypatch.setattr(get_settings(), "internalization_room_mother_tongue_floor", 0.40)
    after = await _an_open_session(db_session, tablet, guide)
    await _the_team_sends_a_take(tablet, after)

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


@pytest.mark.parametrize("floor", ["1.5", "-0.1"])
def test_a_floor_outside_zero_to_one_is_refused_at_boot(
    monkeypatch: pytest.MonkeyPatch, floor: str
) -> None:
    monkeypatch.setenv("INTERNALIZATION_ROOM_MOTHER_TONGUE_FLOOR", floor)

    with pytest.raises(pydantic.ValidationError):
        Settings(database_url="sqlite+aiosqlite:///./test.db", _env_file=None)


def test_the_production_deploy_names_the_mother_tongue_floor_and_it_is_the_default() -> None:
    deployed = deploy_env_vars("deploy.yml")

    default = Settings.model_fields["internalization_room_mother_tongue_floor"].default
    assert float(deployed["INTERNALIZATION_ROOM_MOTHER_TONGUE_FLOOR"]) == default


async def test_after_a_turn_in_words_the_stored_record_shows_the_language_its_probability_the_mother_tongue_decision_and_the_takes_length(  # noqa: E501
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_session(db_session, tablet, guide)
    the_transcriber_hears(monkeypatch, PORTUGUESE, "pt", 0.9)
    the_take_lasts(monkeypatch, 12_000)

    await _the_team_sends_a_take(tablet, session)

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
    the_transcriber_hears(monkeypatch, TERENA_AS_SPANISH, "spa", 0.7)
    the_take_lasts(monkeypatch, 40_000)

    await _the_team_sends_a_take(tablet, session)

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
    the_transcriber_hears_no_words(monkeypatch)
    the_take_lasts(monkeypatch, 8_000)

    await _the_team_sends_a_take(tablet, session)

    assert await _the_turns_record(db_session, session.id) == {
        "language": None,
        "language_probability": None,
        "mother_tongue": False,
        "take_ms": 8_000,
    }


async def test_a_mother_tongue_note_from_the_golden_door_still_reaches_the_guide_as_the_note_and_its_record_says_mother_tongue(  # noqa: E501
    seam: httpx.AsyncClient, db_session: AsyncSession, guide: ScriptedAgent
) -> None:
    session_id = await a_golden_session(seam)
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
    the_transcriber_hears(monkeypatch, PORTUGUESE, "pt", 0.9, transcript_confidence=0.2)
    the_take_lasts(monkeypatch, 12_000)

    reply = await _the_team_sends_a_take(tablet, session)

    assert reply["classification_pending"] is True, (
        "uma resposta em português com confiança baixa por palavra nunca chegava ao classificador"
    )


async def _a_heard_turn(db_session: AsyncSession, session: IRSession) -> None:
    speech = await hearing.heard_speech(b"audio", language=session.language, settings=settings())
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
    the_models_answer(monkeypatch, INVITATION, None, CONVERSATION, None)
    the_take_lasts(monkeypatch, 4_000)
    session = await create_session(db_session, language="pt", pericope=P)
    session = await append_exchange(
        db_session, session, team_utterance="", guide_response="abertura"
    )
    the_transcriber_hears(monkeypatch, "uma mulher volta para o seu povo", "pt", 0.9)
    await _a_heard_turn(db_session, session)

    the_transcriber_hears(monkeypatch, "pronto, terminamos", "pt", 0.9, transcript_confidence=0.1)
    await _a_heard_turn(db_session, session)

    assert comprehension_of(session).practiced_scene_ids == ["S1"], (
        "o relato de ensaio terminado ouvido com confiança baixa por palavra não creditava a cena"
    )
