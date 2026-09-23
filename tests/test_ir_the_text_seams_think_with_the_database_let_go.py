"""Her runner's two seams let go of their reads before the models think.

The Guide, the Validator and the analyst read `in_transaction()` on the request's own session
when they are called, and hand the call on to the harness's doubles.
"""

from __future__ import annotations

import sys
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import text_seam
from app.core.config import get_settings
from tests.text_seam_harness import RUNNER_KEY, TEAM_LINE, the_app, the_models_answer

SEAM = "/api/internalization-room/text-seam"


async def _settled_later(**_: Any) -> None:
    return None


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        get_settings(), "internalization_room_runner_key", RUNNER_KEY, raising=False
    )
    monkeypatch.setattr(text_seam, "settle_coverage", _settled_later)
    async with httpx.AsyncClient(
        transport=ASGITransport(app=the_app(db_session)),
        base_url="http://test",
        headers={"X-Access-Code": RUNNER_KEY},
    ) as c:
        yield c


def _watched(
    monkeypatch: pytest.MonkeyPatch, module: str, db: AsyncSession, held: dict[str, bool]
) -> None:
    answers = sys.modules[module].call_agent

    async def thinks(*, system_prompt: str, **kwargs: Any) -> str:
        role = "validator" if "corrected_response" in system_prompt else "guide"
        held[role] = db.in_transaction()
        return await answers(system_prompt=system_prompt, **kwargs)

    monkeypatch.setattr(sys.modules[module], "call_agent", thinks)


async def test_a_text_turn_is_thought_with_the_database_let_go_not_held_open(
    client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    the_models_answer(monkeypatch)
    created = await client.post(
        f"{SEAM}/session", json={"pericopeId": "P01", "language": "Brazilian Portuguese"}
    )
    session_id = created.json()["sessionId"]
    await client.post(f"{SEAM}/turn", json={"sessionId": session_id, "kickoff": True})
    held: dict[str, bool] = {}
    _watched(monkeypatch, "app.services.internalization_room.run_turn", db_session, held)

    answered = await client.post(f"{SEAM}/turn", json={"sessionId": session_id, "text": TEAM_LINE})

    assert answered.status_code == 200, answered.text
    assert held == {"guide": False, "validator": False}, (
        "a leitura da sessão na costura de texto ficava aberta pelo Guia e pelo Validador"
    )
