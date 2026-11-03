"""ENG-1378 (b) — her runner's turns keep their retelling verdicts as the tablet's do.

The Golden door settles inline and hands the settle the turn it just wrote; its words arrive
as text, so a verdict is kept and a take never is.
"""

from __future__ import annotations

import json
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
from tests.text_seam_harness import BEARER, GOLDEN, RUNNER_KEY, ScriptedAgent, the_app
from tests.turn_harness import the_room_agent_is


@asynccontextmanager
async def _handed(db_session: AsyncSession) -> AsyncIterator[AsyncSession]:
    yield db_session


@pytest.fixture()
def verdict(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    said: dict[str, Any] = {}

    async def reader(**_: Any) -> str:
        return json.dumps({"decisions": [], **said})

    the_room_agent_is(monkeypatch, turn=ScriptedAgent([]), classifier=reader)
    return said


@pytest.fixture()
async def client(db_session: AsyncSession, verdict, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        get_settings(), "internalization_room_runner_key", RUNNER_KEY, raising=False
    )
    monkeypatch.setattr(background, "AsyncSessionLocal", lambda: _handed(db_session))
    transport = ASGITransport(app=the_app(db_session))
    async with httpx.AsyncClient(transport=transport, base_url="http://test", headers=BEARER) as c:
        yield c


async def test_each_golden_turn_keeps_its_verdict_under_its_own_number(
    client: httpx.AsyncClient, verdict: dict[str, Any], db_session: AsyncSession
) -> None:
    created = await client.post(f"{GOLDEN}/session", json={"pericopeId": "P01", "language": "pt"})
    session_id = created.json()["sessionId"]
    opened = await client.post(
        f"{GOLDEN}/turn", json={"sessionId": session_id, "roomNote": "session_start"}
    )
    assert opened.status_code == 200, opened.text

    for approved in (False, True):
        verdict["retelling"] = {"scope": "S1", "approved": approved}
        told = await client.post(
            f"{GOLDEN}/turn", json={"sessionId": session_id, "teamText": "A fome levou a família."}
        )
        assert told.status_code == 200, told.text

    db_session.expire_all()
    assert (await room.get_session(db_session, session_id)).retellings == {
        "1": {"scope": "S1", "approved": False},
        "2": {"scope": "S1", "approved": True},
    }, "o runner dela contava a cena e o veredito da porta dourada caía em outro turno"
