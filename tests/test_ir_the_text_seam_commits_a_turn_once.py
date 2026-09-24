"""The text seam's own turn, counted the way `test_ir_a_voiced_turn_commits_once.py` counts
the voiced one: at the engine, by every `commit` event that carried a write, never by reading
the code back.

The seam is `text_seam.py`'s door, not `sessions.py`'s — the voiced turn already proved the
service layer lands a turn in one UPDATE (ENG-1021); what was still open here was whether the
seam's own route asked for that UPDATE once or asked `_land` for two.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import text_seam
from app.core.config import get_settings
from app.services import internalization_room as room
from tests.room_harness import counting_commits
from tests.text_seam_harness import GUIDE_LINE, RUNNER_KEY, TEAM_LINE, the_app, the_models_answer

SEAM = "/api/internalization-room/text-seam"


async def _settled_later(**_: Any) -> None:
    return None


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        get_settings(), "internalization_room_runner_key", RUNNER_KEY, raising=False
    )
    the_models_answer(monkeypatch)
    monkeypatch.setattr(text_seam, "settle_coverage", _settled_later)

    async def _never_voiced(text: str, **_: Any) -> None:
        raise AssertionError(f"a costura pediu um clipe ao sintetizador: {text!r}")

    monkeypatch.setattr(room, "synthesize_facilitator_speech", _never_voiced)

    async with httpx.AsyncClient(
        transport=ASGITransport(app=the_app(db_session)),
        base_url="http://test",
        headers={"X-Access-Code": RUNNER_KEY},
    ) as c:
        yield c


@pytest.fixture()
def commits(test_engine) -> Iterator[list[object]]:
    with counting_commits(test_engine) as counted:
        yield counted


async def _a_session(client: httpx.AsyncClient) -> str:
    created = await client.post(
        f"{SEAM}/session", json={"pericopeId": "P01", "language": "Brazilian Portuguese"}
    )
    assert created.status_code == 200, created.text
    return created.json()["sessionId"]


async def test_a_text_seam_opening_reaches_the_database_in_one_commit(
    client: httpx.AsyncClient, commits: list[object]
) -> None:
    session_id = await _a_session(client)
    commits.clear()

    kicked = await client.post(f"{SEAM}/turn", json={"sessionId": session_id, "kickoff": True})

    assert kicked.status_code == 200, kicked.text
    assert len(commits) == 1, (
        "a abertura da costura gravava a comprehension e a primeira fala em dois commits"
    )


async def test_a_text_turn_reaches_the_database_in_one_commit_not_two(
    client: httpx.AsyncClient, db_session: AsyncSession, commits: list[object]
) -> None:
    session_id = await _a_session(client)
    await client.post(f"{SEAM}/turn", json={"sessionId": session_id, "kickoff": True})
    commits.clear()

    answered = await client.post(f"{SEAM}/turn", json={"sessionId": session_id, "text": TEAM_LINE})

    assert answered.status_code == 200, answered.text
    assert len(commits) == 1, (
        "o turno de texto gravava a comprehension e as mensagens em dois commits, cada um"
        " com o seu refresh da linha inteira"
    )
    session = await room.get_session(db_session, session_id)
    assert [m["text"] for m in session.messages if m["role"] == "guide"][-1] == GUIDE_LINE
