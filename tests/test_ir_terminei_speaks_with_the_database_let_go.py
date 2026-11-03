"""`terminei` lets go of its read before any model or voice is called.

Each double reads `in_transaction()` on the request's own session at the moment it is called,
which is the session every read of the press ran on: a transaction still open there is a
pooled connection held idle through the analyst, the Speaker, the Validator or the voice.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.room_harness import (
    played_every_part,
    press_terminei,
    rehearsed_in_parts,
    room_client,
)
from tests.turn_harness import the_room_agent_is


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    async with room_client(db_session, monkeypatch) as door:
        yield door


@pytest.fixture()
def held(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> dict[str, bool]:
    from app.api.internalization_room import back_translation as bt_api

    seen: dict[str, bool] = {}

    async def analyst(*, system_prompt: str, user_content: str, **_: Any) -> str:
        seen["analyst"] = db_session.in_transaction()
        return '{"evidence_sufficient": true, "findings": []}'

    async def speaker(*, system_prompt: str, user_content: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            seen["validator"] = db_session.in_transaction()
            return json.dumps({"verdict": "pass", "issues": []})
        seen["guide"] = db_session.in_transaction()
        return "Vocês contaram bem."

    async def voice(text: str, *_: Any, **__: Any):
        seen["voice"] = db_session.in_transaction()
        return (type("Voiced", (), {"key": "clipe-1"})(), 0)

    the_room_agent_is(monkeypatch, analyst=analyst)
    the_room_agent_is(monkeypatch, turn=speaker)
    monkeypatch.setattr(bt_api.room, "synthesize_facilitator_speech", voice)
    return seen


async def test_the_verdict_is_read_and_voiced_with_the_database_let_go_not_held_open(
    client: httpx.AsyncClient, db_session: AsyncSession, held: dict[str, bool]
) -> None:
    session, parts = await rehearsed_in_parts(db_session, 1)

    answered = await press_terminei(
        client, session.id, report=played_every_part([part.id for part in parts])
    )

    assert answered.status_code == 200, answered.text
    assert held == {"analyst": False, "guide": False, "validator": False, "voice": False}, (
        "as leituras do terminei abriam a transação e a conexão ficava presa pelo analista,"
        " pelo Falante, pelo Validador e pela voz"
    )
