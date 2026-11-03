"""The Golden door's opening is refused only to a session that holds a Guide line.

A room note and a team entry are not the Guide's Opening, so a session holding only those is
not opened and its «session_start» still drafts the Opening, as the tablet's turn door does.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import golden_doors
from app.core.config import get_settings
from app.db.models.internalization_room import IRSession
from app.services import internalization_room as room
from tests.text_seam_harness import (
    BEARER,
    GOLDEN,
    GUIDE_LINE,
    RUNNER_KEY,
    the_app,
    the_models_answer,
)


async def _settled_later(**_: Any) -> None:
    return None


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        get_settings(), "internalization_room_runner_key", RUNNER_KEY, raising=False
    )
    the_models_answer(monkeypatch)
    monkeypatch.setattr(golden_doors, "settle_coverage", _settled_later)

    async with httpx.AsyncClient(
        transport=ASGITransport(app=the_app(db_session)),
        base_url="http://test",
        headers=BEARER,
    ) as c:
        yield c


async def test_a_session_holding_a_room_note_and_a_team_entry_still_gets_its_golden_opening(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    created = await client.post(
        f"{GOLDEN}/session", json={"pericopeId": "P01", "language": "Brazilian Portuguese"}
    )
    session_id = created.json()["sessionId"]
    await db_session.execute(
        update(IRSession)
        .where(IRSession.id == session_id)
        .values(
            messages=[
                {"role": "room", "text": "[a sessão acabou de começar]"},
                {"role": "team", "text": "Noemi voltou para Belém"},
            ]
        )
    )
    await db_session.commit()

    kicked = await client.post(
        f"{GOLDEN}/turn", json={"sessionId": session_id, "roomNote": "session_start"}
    )

    assert kicked.status_code == 200, kicked.text
    session = await room.get_session(db_session, session_id)
    assert [m["text"] for m in session.messages if m["role"] == "guide"] == [GUIDE_LINE]
