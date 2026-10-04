from __future__ import annotations

import asyncio
import json
import logging
import time
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

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
from app.services.platform import tts

PREFIX = "/api/internalization-room"
KEY = "sala-de-teste"
P = "P03"
GUIDE_LINE = "Vamos ficar nesta cena. O que vocês contariam uns aos outros sobre ela?"


class _Models:
    async def create(self, **kwargs: Any) -> SimpleNamespace:
        system = "".join(block["text"] for block in kwargs["system"])
        validating = "corrected_response" in system
        text = json.dumps({"verdict": "pass", "issues": []}) if validating else GUIDE_LINE
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


class _Bucket:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def get(self, key: str) -> bytes | None:
        return self.objects.get(key)

    async def exists(self, key: str) -> bool:
        return key in self.objects

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = data


async def _hearing(audio: bytes, **_: Any) -> HeardSpeech:
    return HeardSpeech(text="Noemi voltou para Belém com Rute no tempo da colheita")


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
def elevenlabs() -> SimpleNamespace:
    return SimpleNamespace(
        get=AsyncMock(return_value=SimpleNamespace(status_code=200, content=b"", text="")),
        post=AsyncMock(return_value=SimpleNamespace(status_code=200, content=b"mp3", text="")),
    )


@pytest.fixture()
async def client(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, elevenlabs: SimpleNamespace
):
    from fastapi import FastAPI

    from app.api.internalization_room import router
    from app.api.internalization_room import sessions as sessions_api
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    monkeypatch.setattr(get_settings(), "internalization_room_api_key", KEY, raising=False)
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "sk-ant-fake", raising=False)
    monkeypatch.setattr(get_settings(), "elevenlabs_api_key", "fake-elevenlabs", raising=False)
    monkeypatch.setattr(sessions_api, "heard_speech", _hearing)
    monkeypatch.setattr(sessions_api, "settle_coverage", _settles_nothing)
    monkeypatch.setattr(
        llm.anthropic, "AsyncAnthropic", lambda **_: SimpleNamespace(messages=_Models())
    )
    monkeypatch.setattr(tts, "_make_client", lambda: elevenlabs)
    monkeypatch.setattr(tts, "_default_store", lambda _: _Bucket())

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
        db_session, session, team_utterance="", guide_response="Quem aparece nesta parte?"
    )
    state = comprehension_of(session)
    state.active_probe = ActiveProbe(id="probe-1", purpose=ProbePurpose.RECORDING_HANDOFF_CONSENT)
    return await save_comprehension(db_session, session, state)


async def test_a_spoken_turn_warms_the_elevenlabs_connection_once_when_the_validator_starts(
    client: httpx.AsyncClient, waiting_room: IRSession, elevenlabs: SimpleNamespace
) -> None:
    answered = await client.post(
        f"{PREFIX}/sessions/{waiting_room.id}/turns",
        headers={"X-Room-Key": KEY},
        files={"file": ("answer.m4a", b"sixteen bytes!!!", "audio/m4a")},
    )

    assert answered.status_code == 200
    assert elevenlabs.get.await_count == 1, (
        "o turno passou por um único Validador, e o aquecimento devia ter disparado uma vez"
    )
    args, kwargs = elevenlabs.get.await_args
    assert "/v1/models" in args[0], "o aquecimento deveria bater num endpoint sem custo"
    assert "json" not in kwargs, "um GET de aquecimento não carrega o texto a sintetizar"


async def test_a_redraft_still_only_warms_the_connection_once(
    monkeypatch: pytest.MonkeyPatch, elevenlabs: SimpleNamespace
) -> None:
    from app.services.internalization_room.coverage import initial_state
    from app.services.internalization_room.run_turn import run_turn
    from tests.turn_harness import GUIDE, VALIDATOR, FakeAgent, P, settings, the_agent_answers

    monkeypatch.setattr(tts, "_make_client", lambda: elevenlabs)
    agent = the_agent_answers(
        monkeypatch,
        FakeAgent(
            verdicts=[
                {"verdict": "regenerate", "issues": [{"problem": "imported_knowledge"}]},
                {"verdict": "pass", "issues": []},
            ]
        ),
    )

    outcome = await run_turn(
        session_language="Portuguese",
        language_code="pt",
        transcript="alguma coisa",
        coverage_state=initial_state(P),
        messages=[],
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        pericope_num=P,
        settings=settings().model_copy(update={"elevenlabs_api_key": "fake-elevenlabs"}),
    )
    await asyncio.gather(*tts._PENDING_WARMUPS, return_exceptions=True)

    assert agent.calls == ["guide", "validator", "guide", "validator"], (
        "o cenário precisa de um redraft de verdade — uma segunda passagem pelo Guia — "
        "não só de uma segunda leitura do mesmo rascunho"
    )
    assert outcome.redrafts == 1
    assert elevenlabs.get.await_count == 1, (
        "um redraft manda o Validador ler de novo numa segunda tentativa, e o aquecimento "
        "não pode disparar de novo por isso"
    )


async def _slow_failure(*_: Any, **__: Any) -> SimpleNamespace:
    await asyncio.sleep(2.0)
    raise RuntimeError("connection refused")


async def test_a_warm_up_that_fails_never_slows_the_turn_and_logs_only_the_exceptions_name(
    client: httpx.AsyncClient,
    waiting_room: IRSession,
    elevenlabs: SimpleNamespace,
    caplog: pytest.LogCaptureFixture,
) -> None:
    from app.services.platform import tts

    elevenlabs.get = AsyncMock(side_effect=_slow_failure)

    with caplog.at_level(logging.WARNING):
        started = time.monotonic()
        answered = await client.post(
            f"{PREFIX}/sessions/{waiting_room.id}/turns",
            headers={"X-Room-Key": KEY},
            files={"file": ("answer.m4a", b"sixteen bytes!!!", "audio/m4a")},
        )
        elapsed = time.monotonic() - started

        assert answered.status_code == 200, "uma falha do aquecimento não pode derrubar o turno"
        assert elapsed < 0.5, "o turno não pode esperar pelo aquecimento em segundo plano"

        await asyncio.gather(*tts._PENDING_WARMUPS, return_exceptions=True)

    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any("RuntimeError" in message for message in warnings), (
        "a falha do aquecimento devia deixar um aviso nomeando a exceção"
    )
    assert not any("connection refused" in message for message in warnings), (
        "o aviso não pode carregar o corpo/mensagem da exceção, só o nome da classe"
    )
    assert not any("fake-elevenlabs" in message for message in warnings), (
        "o aviso não pode carregar a chave da ElevenLabs"
    )
