"""A provider that hangs is an error inside one generous bound, and every call says how long.

No call the room made had a clock on it: the SDK's own default was ten minutes and two
hidden retries on top, so a provider that stopped answering was half an hour of silence in
front of a team, with nothing to tap. Her reference is one bound at the outer edge — a
route that accepts 300 s — and no clock below it: a turn legitimately runs from 10 s to
56 s, and the wait is held by the acknowledgement, not by a deadline.
"""

import asyncio
import json
import logging
import time
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx
import pytest

from app.core.config import Settings
from app.core.exceptions import UpstreamServiceError
from app.services.internalization_room import llm
from app.services.internalization_room.coverage import initial_state
from app.services.internalization_room.run_turn import run_turn
from tests.turn_harness import GUIDE, VALIDATOR, P

MODEL = "claude-fable-5-1"
DRAFT = "Vamos ficar nesta cena. O que vocês contariam?"


def _settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "database_url": "sqlite+aiosqlite:///./test.db",
        "anthropic_api_key": "sk-ant-fake",
        "tripod_voice_model": MODEL,
    }
    base.update(overrides)
    return Settings(**base)


def _reply(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        stop_reason="end_turn",
        model=MODEL,
        usage=SimpleNamespace(
            input_tokens=10,
            output_tokens=5,
            cache_read_input_tokens=0,
            cache_creation_input_tokens=0,
            cache_creation=None,
        ),
    )


class _Scripted:
    """The Guide and the Validator answering in turn, remembering what each call carried."""

    def __init__(self) -> None:
        self.kwargs: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> SimpleNamespace:
        self.kwargs.append(kwargs)
        if "corrected_response" in str(kwargs["system"]):
            return _reply(json.dumps({"verdict": "pass", "issues": []}))
        return _reply(DRAFT)


class _Hung:
    """A provider that never answers, and says whether the room ever let go of the request."""

    def __init__(self) -> None:
        self.let_go = False

    async def create(self, **_: Any) -> SimpleNamespace:
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.let_go = True
            raise
        raise AssertionError("unreachable: nothing sets the event")


@pytest.fixture
def the_client(monkeypatch: pytest.MonkeyPatch):
    def _install(messages: Any) -> dict[str, Any]:
        built: dict[str, Any] = {}

        def _build(**options: Any) -> SimpleNamespace:
            built.update(options)
            return SimpleNamespace(messages=messages)

        monkeypatch.setattr(llm.anthropic, "AsyncAnthropic", _build)
        return built

    return _install


async def test_the_guide_and_the_validator_each_carry_the_deadline_and_no_retries(
    the_client,
) -> None:
    messages = _Scripted()
    options = the_client(messages)

    outcome = await run_turn(
        session_language="Portuguese",
        language_code="pt",
        transcript="me conta mais sobre Rute",
        coverage_state=initial_state(P),
        messages=[],
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        pericope_num=P,
        settings=_settings(),
    )

    assert outcome.speech == DRAFT
    assert [call["model"] for call in messages.kwargs] == [MODEL, MODEL]
    assert [call["timeout"] for call in messages.kwargs] == [300.0, 300.0], (
        "nenhuma chamada tinha relógio: o SDK esperava 600 s por resposta, e a equipe "
        "ficava diante de um círculo que nunca respondia nem falhava"
    )
    assert "max_retries" not in options, (
        "zerar o retry do SDK deixava a sala sozinha contra uma rejeição passageira: nem o "
        "SDK nem a sala tentavam de novo, e um 429 de um segundo virava 502 na hora"
    )


async def test_a_provider_that_hangs_is_an_error_inside_the_bound_and_the_request_is_let_go(
    the_client, caplog: pytest.LogCaptureFixture
) -> None:
    hung = _Hung()
    the_client(hung)
    started = time.monotonic()

    with (
        caplog.at_level(logging.WARNING, logger="app.services.internalization_room.llm"),
        pytest.raises(UpstreamServiceError) as raised,
    ):
        await asyncio.wait_for(
            llm.call_agent(
                role="guide",
                system_prompt="s",
                user_content="u",
                timeout_ms=50,
                settings=_settings(),
            ),
            timeout=5,
        )

    assert time.monotonic() - started < 5, "o limite é o que encerra a espera, não o suite"
    assert MODEL in str(raised.value), "o erro nomeia o degrau que não respondeu"
    assert hung.let_go is True, (
        "o pedido seguia em voo depois de a sala desistir dele: uma conexão pendurada por "
        "turno, e o provedor ainda cobrando por uma resposta que ninguém ia ouvir"
    )
    timed_out = [
        record
        for record in caplog.records
        if record.name == "app.services.internalization_room.llm" and hasattr(record, "outcome")
    ]
    assert len(timed_out) == 1, "a chamada que estourou não deixava linha de uso nenhuma"
    assert "[llm-usage]" in timed_out[0].getMessage()
    assert timed_out[0].outcome == "timeout"
    assert timed_out[0].role == "guide" and timed_out[0].rung == MODEL
    assert 0 <= timed_out[0].latency_ms < 5000


async def test_a_call_cut_short_by_the_turns_own_bound_still_says_who_was_waiting(
    the_client, caplog: pytest.LogCaptureFixture
) -> None:
    """The route's bound starts before the call's, so on a turn it is the one that fires.

    The cancellation reaches the call from outside, not from its own clock — and a turn
    that ended with "o turno não respondeu" and no line under it could not say whether the
    Guide or the Validator was the one still waiting.
    """
    hung = _Hung()
    the_client(hung)

    with (
        caplog.at_level(logging.WARNING, logger="app.services.internalization_room.llm"),
        pytest.raises(TimeoutError),
    ):
        await asyncio.wait_for(
            llm.call_agent(
                role="validator", system_prompt="s", user_content="u", settings=_settings()
            ),
            timeout=0.05,
        )

    assert hung.let_go is True
    (cut,) = _usage_lines(caplog)
    assert cut.outcome == "timeout" and cut.role == "validator" and cut.rung == MODEL, (
        "o limite da rota disparava antes do da chamada, e a chamada cancelada não deixava "
        "linha nenhuma: o log dizia que o turno não respondeu, e não quem estava esperando"
    )
    assert isinstance(cut.latency_ms, int)


def _usage_lines(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [
        record
        for record in caplog.records
        if record.name == "app.services.internalization_room.llm"
        and "[llm-usage]" in record.getMessage()
    ]


async def test_an_answered_call_says_who_asked_how_long_it_took_and_that_it_was_ok(
    the_client, caplog: pytest.LogCaptureFixture
) -> None:
    the_client(_Scripted())

    with caplog.at_level(logging.INFO, logger="app.services.internalization_room.llm"):
        await llm.call_agent(
            role="validator", system_prompt="s", user_content="u", settings=_settings()
        )

    (answered,) = _usage_lines(caplog)
    assert answered.role == "validator" and answered.rung == MODEL
    assert isinstance(answered.latency_ms, int)
    assert answered.outcome == "ok", (
        "a linha da chamada que respondeu não dizia como terminou, e a que falhou não dizia "
        "nem quem perguntou nem quanto esperou: as duas se liam juntas e não se somavam"
    )


class _Refusing:
    def __init__(self, failure: Exception) -> None:
        self.failure = failure

    async def create(self, **_: Any) -> SimpleNamespace:
        raise self.failure


async def test_a_refused_call_says_who_asked_how_long_it_waited_and_that_it_erred(
    the_client, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    the_client(
        _Refusing(
            anthropic.InternalServerError(
                "Overloaded", response=httpx.Response(status_code=529, request=request), body=None
            )
        )
    )
    monkeypatch.setattr(llm, "_RETRY_WAIT_S", 0)

    with (
        caplog.at_level(logging.WARNING, logger="app.services.internalization_room.llm"),
        pytest.raises(UpstreamServiceError),
    ):
        await llm.call_agent(
            role="classifier", system_prompt="s", user_content="u", settings=_settings()
        )

    first, second = _usage_lines(caplog)
    for refused in (first, second):
        assert refused.status == 529 and refused.rung == MODEL
        assert refused.role == "classifier", (
            "sem o papel, a linha não separa o Guia do classificador"
        )
        assert isinstance(refused.latency_ms, int)
        assert refused.outcome == "error"
    assert (first.attempt, second.attempt) == (1, 2), (
        "um 529 é uma pressa passageira: a sala tenta o mesmo degrau uma segunda vez antes "
        "de desistir, e cada tentativa deixa sua própria linha de uso"
    )
