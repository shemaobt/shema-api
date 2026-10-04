"""How long each stage of `terminei` took, read off the log line the route leaves.

The analyst, the Guide, the Validator and the voice each answer after a known delay, through
the Anthropic client and the synthesizer rather than above them, so the times in the line can
only have come from the stopwatch the route opens.
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
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.internalization_room import llm, usage
from tests.room_harness import (
    a_piece_still_to_be_told,
    played_every_part,
    press_terminei,
    rehearsed_in_parts,
    room_client,
    stretch_on,
)

ANALYST_MS = 70
GUIDE_MS = 60
VALIDATOR_MS = 90
VOICE_MS = 50


class _SlowModels:
    async def create(self, **kwargs: Any) -> SimpleNamespace:
        system = kwargs["system"]
        system = system if isinstance(system, str) else "".join(b["text"] for b in system)
        if kwargs["messages"][-1]["content"] == "Compare a tradução com o mapa.":
            delay, text = ANALYST_MS, '{"evidence_sufficient": true, "findings": []}'
        elif "corrected_response" in system:
            delay, text = VALIDATOR_MS, json.dumps({"verdict": "pass", "issues": []})
        else:
            delay, text = GUIDE_MS, "Vocês contaram bem."
        await asyncio.sleep(delay / 1000)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=text)],
            stop_reason="end_turn",
            model=kwargs["model"],
            usage=SimpleNamespace(
                input_tokens=10,
                output_tokens=10,
                cache_read_input_tokens=0,
                cache_creation_input_tokens=0,
                cache_creation=None,
            ),
        )


async def _slow_voice(text: str, *_: Any, **__: Any) -> tuple[Any, bool]:
    await asyncio.sleep(VOICE_MS / 1000)
    return type("Voiced", (), {"key": "clipe-1"})(), False


@pytest.fixture(autouse=True)
def _forget_which_rung_answered():
    llm._SETTLED.clear()
    usage.forget_sessions()
    yield
    llm._SETTLED.clear()
    usage.forget_sessions()


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    from app.api.internalization_room import back_translation as bt_api
    from app.core.config import get_settings

    models = SimpleNamespace(messages=_SlowModels())
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "sk-ant-fake", raising=False)
    monkeypatch.setattr(llm.anthropic, "AsyncAnthropic", lambda **_: models)
    monkeypatch.setattr(bt_api.room, "synthesize_facilitator_speech", _slow_voice)
    async with room_client(db_session, monkeypatch) as door:
        yield door


async def test_terminei_says_how_long_the_reading_the_verdict_and_the_voice_each_took(
    client: httpx.AsyncClient, db_session: AsyncSession, caplog: pytest.LogCaptureFixture
) -> None:
    session, parts = await rehearsed_in_parts(db_session, 1)

    with caplog.at_level(logging.INFO):
        answered = await press_terminei(
            client, session.id, report=played_every_part([part.id for part in parts])
        )

    assert answered.status_code == 200, answered.text
    lines = [r.getMessage() for r in caplog.records if "[bt-timing]" in r.getMessage()]
    assert len(lines) == 1, "o terminei nunca tinha sido cronometrado"
    assert f"session={session.id} " in lines[0]
    spent = {name: int(ms) for name, ms in re.findall(r" (\w+)=(\d+)ms", lines[0])}
    assert spent["analyst"] >= ANALYST_MS
    assert spent["guide"] >= GUIDE_MS
    assert spent["validator"] >= VALIDATOR_MS
    assert spent["voice"] >= VOICE_MS, "a voz do veredito não era medida"
    assert "db_write" in spent, "a gravação do veredito não era medida"
    assert spent["total"] >= ANALYST_MS + GUIDE_MS + VALIDATOR_MS + VOICE_MS


def _stages(caplog: pytest.LogCaptureFixture) -> dict[str, int]:
    lines = [r.getMessage() for r in caplog.records if "[bt-timing]" in r.getMessage()]
    assert len(lines) == 1, lines
    return {name: int(ms) for name, ms in re.findall(r" (\w+)=(\d+)ms", lines[0])}


async def test_letting_the_read_go_before_the_verdict_is_timed_on_its_own_not_hidden_in_total(
    client: httpx.AsyncClient, db_session: AsyncSession, caplog: pytest.LogCaptureFixture
) -> None:
    session, parts = await rehearsed_in_parts(db_session, 1)

    with caplog.at_level(logging.INFO):
        answered = await press_terminei(
            client, session.id, report=played_every_part([part.id for part in parts])
        )

    assert answered.status_code == 200, answered.text
    assert "db_let_go" in _stages(caplog), (
        "o COMMIT que solta a leitura antes do veredito só aparecia somado no total"
    )


async def test_letting_the_read_go_before_naming_an_unheard_part_is_timed_on_its_own_too(
    client: httpx.AsyncClient, db_session: AsyncSession, caplog: pytest.LogCaptureFixture
) -> None:
    session, (first, _second) = await rehearsed_in_parts(db_session, 2)

    with caplog.at_level(logging.INFO):
        answered = await press_terminei(client, session.id, report=played_every_part([first.id]))

    assert answered.status_code == 200, answered.text
    assert "db_let_go" in _stages(caplog), (
        "o COMMIT que solta a leitura antes da fala de quem não ouviu só aparecia somado no total"
    )


async def test_letting_the_read_go_before_naming_an_untold_stretch_is_timed_on_its_own_too(
    client: httpx.AsyncClient, db_session: AsyncSession, caplog: pytest.LogCaptureFixture
) -> None:
    session, (part,) = await rehearsed_in_parts(db_session, 1)
    await a_piece_still_to_be_told(db_session, session, await stretch_on(db_session, session, part))

    with caplog.at_level(logging.INFO):
        answered = await press_terminei(client, session.id)

    assert answered.status_code == 200, answered.text
    assert "db_let_go" in _stages(caplog), (
        "o COMMIT que solta a leitura antes do recado do não contado só aparecia somado no total"
    )
