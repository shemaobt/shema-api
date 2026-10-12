"""ENG-1378 — a name the team says is engaged even when the coverage reader fails.

The name check needs no model (her `tracker.ts:70-76`, PRD ch.13), so a turn whose
classifier raises still leaves Naomi engaged, and the Guide reads her among what the team
worked with on the next turn — the ledger is rendered from the stored coverage before the
Guide speaks, as hers is (`liveTurn.ts:503`). Ours left the tracker untouched on a failed
reading (`classify_coverage.py:266-268`), so a «Noemi» said on that turn was never counted.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.services import internalization_room as room
from app.services.internalization_room import background
from app.services.internalization_room.llm import CACHE_BREAK
from tests.text_seam_harness import BEARER, GOLDEN, RUNNER_KEY, ScriptedAgent, the_app
from tests.turn_harness import the_room_agent_is

ENGAGED_LINE = "WORKED WITH BY THE TEAM (engaged):"


@asynccontextmanager
async def _handed(db_session: AsyncSession) -> AsyncIterator[AsyncSession]:
    yield db_session


@pytest.fixture()
def guide(monkeypatch: pytest.MonkeyPatch) -> ScriptedAgent:
    agent = ScriptedAgent(["Vamos ouvir uma história juntos.", None, "Isso.", None])

    async def the_reader_is_down(**_: Any) -> str:
        raise RuntimeError("o classificador caiu")

    the_room_agent_is(monkeypatch, turn=agent, classifier=the_reader_is_down)
    return agent


@pytest.fixture()
async def client(db_session: AsyncSession, guide, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        get_settings(), "internalization_room_runner_key", RUNNER_KEY, raising=False
    )

    async def _never_voiced(text: str, **_: Any) -> None:
        raise AssertionError(f"a costura pediu um clipe ao sintetizador: {text!r}")

    monkeypatch.setattr(room, "synthesize_facilitator_speech", _never_voiced)
    monkeypatch.setattr(background, "AsyncSessionLocal", lambda: _handed(db_session))
    transport = ASGITransport(app=the_app(db_session))
    async with httpx.AsyncClient(transport=transport, base_url="http://test", headers=BEARER) as c:
        yield c


async def _turn(client: httpx.AsyncClient, session_id: str, said: str) -> None:
    answered = await client.post(f"{GOLDEN}/turn", json={"sessionId": session_id, "teamText": said})
    assert answered.status_code == 200, answered.text


async def test_noemi_on_a_turn_whose_classifier_fails_is_read_as_worked_on_the_next_turn(
    client: httpx.AsyncClient, guide: ScriptedAgent
) -> None:
    created = await client.post(f"{GOLDEN}/session", json={"pericopeId": "P01", "language": "pt"})
    assert created.status_code == 200, created.text
    session_id = created.json()["sessionId"]
    opened = await client.post(
        f"{GOLDEN}/turn", json={"sessionId": session_id, "roomNote": "session_start"}
    )
    assert opened.status_code == 200, opened.text

    await _turn(client, session_id, "A Noemi ficou.")
    await _turn(client, session_id, "Sim.")

    ledger = guide.guide_systems[2].partition(CACHE_BREAK)[2]
    worked = [line for line in ledger.splitlines() if line.startswith(ENGAGED_LINE)]
    assert worked and "Naomi" in worked[0], (
        "o classificador caía e a Noemi que a equipe disse não chegava ao livro-razão do Guia"
    )
