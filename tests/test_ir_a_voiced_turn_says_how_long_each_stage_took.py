"""How long each stage of a voiced turn took, in the log and in the answer's own header.

The whole turn runs through the route with every provider stubbed at its edge — the
transcriber, the Anthropic client, the voice — and each stub takes a known time. The
stages the ticket names are expected by name, and each one to have taken at least what its
stub was made to take: a number that can only have come from the stub's own clock, never
recomputed the way the stopwatch computes it.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession
from app.services.internalization_room import llm, usage
from app.services.internalization_room.comprehension.probe import ActiveProbe, ProbePurpose
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.sessions import (
    append_exchange,
    comprehension_of,
    create_session,
    save_comprehension,
)
from app.services.platform.tts import SynthesizedSpeech
from tests.clip_flight_harness import voiced_through

PREFIX = "/api/internalization-room"
KEY = "sala-de-teste"
P = "P03"
FIRST_QUESTION = "Quem aparece nesta parte?"
GUIDE_LINE = "Vamos ficar nesta cena. O que vocês contariam uns aos outros sobre ela?"
TEAM_ANSWER = "Noemi voltou para Belém com Rute no tempo da colheita"

HEARING_MS = 40
GUIDE_MS = 60
VALIDATOR_MS = 90
VOICE_MS = 50


class _SlowModels:
    """The Anthropic client, answering the Guide and the Validator each after its own delay."""

    def __init__(self) -> None:
        self.verdicts = ["pass"]

    async def create(self, **kwargs: Any) -> SimpleNamespace:
        system = "".join(block["text"] for block in kwargs["system"])
        validating = "corrected_response" in system
        await asyncio.sleep((VALIDATOR_MS if validating else GUIDE_MS) / 1000)
        text = self._verdict() if validating else GUIDE_LINE
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=text)],
            stop_reason="end_turn",
            model=kwargs["model"],
            usage=SimpleNamespace(
                input_tokens=10,
                output_tokens=10,
                cache_creation_input_tokens=0,
                cache_read_input_tokens=0,
                cache_creation=None,
            ),
        )

    def _verdict(self) -> str:
        verdict = self.verdicts.pop(0) if len(self.verdicts) > 1 else self.verdicts[0]
        issues = [{"problem": "unsupported_claim"}] if verdict == "fail" else []
        return json.dumps({"verdict": verdict, "issues": issues})


async def _slow_hearing(audio: bytes, **_: Any) -> HeardSpeech:
    await asyncio.sleep(HEARING_MS / 1000)
    return HeardSpeech(text=TEAM_ANSWER)


async def _slow_voice(text: str, **_: Any) -> tuple[SynthesizedSpeech, bool]:
    await asyncio.sleep(VOICE_MS / 1000)
    entry = SynthesizedSpeech(
        audio=b"audio", mime_type="audio/mpeg", etag="e", cached=False, key="tts/voice/m/f/l.mp3"
    )
    return entry, False


async def _settles_nothing(**_: Any) -> None:
    return None


@pytest.fixture(autouse=True)
def _forget_which_rung_answered():
    llm._SETTLED.clear()
    usage.forget_sessions()
    yield
    llm._SETTLED.clear()
    usage.forget_sessions()


@pytest.fixture()
def models() -> _SlowModels:
    return _SlowModels()


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, models: _SlowModels):
    from fastapi import FastAPI

    from app.api.internalization_room import router
    from app.api.internalization_room import sessions as sessions_api
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    monkeypatch.setattr(get_settings(), "internalization_room_api_key", KEY, raising=False)
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "sk-ant-fake", raising=False)
    monkeypatch.setattr(sessions_api, "heard_speech", _slow_hearing)
    monkeypatch.setattr(sessions_api.room, "synthesize_facilitator_speech", _slow_voice)
    monkeypatch.setattr(
        sessions_api.room, "facilitator_speech_to_come", voiced_through(_slow_voice)
    )
    monkeypatch.setattr(sessions_api, "settle_coverage", _settles_nothing)
    monkeypatch.setattr(
        llm.anthropic, "AsyncAnthropic", lambda **_: SimpleNamespace(messages=models)
    )

    test_app = FastAPI()
    test_app.include_router(router, prefix=PREFIX)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture()
async def waiting_room(db_session: AsyncSession) -> IRSession:
    session = await create_session(db_session, language="pt", pericope=P)
    session = await append_exchange(
        db_session, session, team_utterance="", guide_response=FIRST_QUESTION
    )
    state = comprehension_of(session)
    state.active_probe = ActiveProbe(id="probe-1", purpose=ProbePurpose.RECORDING_HANDOFF_CONSENT)
    return await save_comprehension(db_session, session, state)


def _server_timing(response: httpx.Response) -> dict[str, int]:
    return {
        name: int(duration)
        for name, duration in re.findall(r"(\w+);dur=(\d+)", response.headers["Server-Timing"])
    }


async def _the_team_answers(
    client: httpx.AsyncClient, session_id: str, client_timing: str | None = None
) -> httpx.Response:
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/turns",
        headers={"X-Room-Key": KEY},
        files={"file": ("answer.m4a", b"sixteen bytes!!!", "audio/m4a")},
        data={} if client_timing is None else {"client_timing": client_timing},
    )


def _client_timing_lines(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.getMessage() for r in caplog.records if "[client-timing]" in r.getMessage()]


def _timing_lines(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.getMessage() for r in caplog.records if "[turn-timing]" in r.getMessage()]


async def test_a_voiced_turn_answers_with_how_long_each_of_its_stages_took(
    client: httpx.AsyncClient, waiting_room: IRSession, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO):
        answered = await _the_team_answers(client, waiting_room.id)

    assert answered.status_code == 200, answered.text[:300]
    timing = _server_timing(answered)
    assert timing["stt"] >= HEARING_MS, "o tempo do speech-to-text não era medido"
    assert timing["guide"] >= GUIDE_MS, "o tempo do Guia só existia somado ao do Validador"
    assert timing["validator"] >= VALIDATOR_MS
    assert "voice" not in timing and "upload" not in timing, (
        "a resposta esperava a ElevenLabs e o GCS; a voz agora é feita enquanto o tablet a pede"
    )
    assert "db_write" in timing, "a escrita no banco nunca tinha sido cronometrada"
    assert timing["total"] >= HEARING_MS + GUIDE_MS + VALIDATOR_MS

    lines = _timing_lines(caplog)
    assert len(lines) == 1, "um turno falado deixa uma linha só"
    line = lines[0]
    assert f"session={waiting_room.id}" in line
    for name, duration in timing.items():
        assert f"{name}={duration}ms" in line, "a linha e o header diziam números diferentes"
    assert "upload_bytes=16" in line
    assert TEAM_ANSWER not in line and GUIDE_LINE not in line


async def test_a_redrafted_turn_counts_every_draft_and_every_reading_not_only_the_last(
    client: httpx.AsyncClient, waiting_room: IRSession, models: _SlowModels
) -> None:
    models.verdicts = ["fail", "pass"]

    answered = await _the_team_answers(client, waiting_room.id)

    assert answered.status_code == 200, answered.text[:300]
    timing = _server_timing(answered)
    assert timing["guide"] >= 2 * GUIDE_MS, "o redraft apagava o tempo do primeiro rascunho"
    assert timing["validator"] >= 2 * VALIDATOR_MS


async def test_a_turn_whose_write_breaks_still_says_how_long_it_waited_before_breaking(
    client: httpx.AsyncClient,
    waiting_room: IRSession,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    from app.api.internalization_room import sessions as sessions_api

    async def _the_database_goes_away(*_: Any, **__: Any) -> IRSession:
        raise RuntimeError("the database went away")

    monkeypatch.setattr(sessions_api.room, "append_exchange", _the_database_goes_away)

    with caplog.at_level(logging.INFO):
        answered = await _the_team_answers(client, waiting_room.id)

    assert answered.status_code == 500
    lines = _timing_lines(caplog)
    assert len(lines) == 1, "o turno que quebrava não deixava tempo nenhum para trás"
    assert re.search(r" stt=\d+ms guide=\d+ms validator=\d+ms db_write=\d+ms total=\d+ms", lines[0])


async def test_the_tablets_timings_of_its_last_turn_reach_the_same_log_as_the_servers(
    client: httpx.AsyncClient, waiting_room: IRSession, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO):
        answered = await _the_team_answers(
            client, waiting_room.id, client_timing="stop_tap=0;answer_in=2140;sounding=2600"
        )

    assert answered.status_code == 200, answered.text[:300]
    assert _client_timing_lines(caplog) == [
        f"[client-timing] session={waiting_room.id} stop_tap=0;answer_in=2140;sounding=2600"
    ]


async def test_a_turn_that_sends_no_timings_leaves_no_line_for_them(
    client: httpx.AsyncClient, waiting_room: IRSession, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO):
        answered = await _the_team_answers(client, waiting_room.id)

    assert answered.status_code == 200, answered.text[:300]
    assert _client_timing_lines(caplog) == []


@pytest.mark.parametrize(
    "client_timing",
    [
        "stop_tap=0;Rute voltou=12",
        "stop_tap=-3",
        "stop_tap=١٢",
        "stop_tap=0\n",
        "a=1;" * 128 + "b=2",
    ],
    ids=["words", "negative", "non-ascii-digits", "trailing-newline", "longer-than-512"],
)
async def test_timings_the_server_cannot_read_are_dropped_unread_and_never_cost_the_turn(
    client: httpx.AsyncClient,
    waiting_room: IRSession,
    caplog: pytest.LogCaptureFixture,
    client_timing: str,
) -> None:
    with caplog.at_level(logging.INFO):
        answered = await _the_team_answers(client, waiting_room.id, client_timing=client_timing)

    assert answered.status_code == 200, "um campo de telemetria ruim custava o turno da equipe"
    assert _client_timing_lines(caplog) == [f"[client-timing] rejected session={waiting_room.id}"]
