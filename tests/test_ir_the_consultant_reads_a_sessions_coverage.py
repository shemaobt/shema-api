"""ENG-1333 — the consultant reads a session's coverage in her kinds and the ledger the voice reads.

Every case drives the real application through the door the Desk reads by, as a consultant
who belongs to no team.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession
from tests.baker import (
    grant_room_app_role,
    make_language,
    make_project,
    make_user,
    open_ir_session,
)

IR = "/api/internalization-room"
P = "P01"
HER_KINDS = [
    "arc",
    "context",
    "tone",
    "function",
    "scene",
    "being",
    "place",
    "object",
    "time",
    "absence",
    "preserved",
]


@pytest.fixture()
async def client(db_session: AsyncSession) -> AsyncIterator[httpx.AsyncClient]:
    from app.core.database import get_db
    from app.main import app

    async def _get_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_db
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
async def consultant(db_session: AsyncSession) -> dict[str, str]:
    from app.services.auth.issue_tokens import issue_tokens

    user = await make_user(db_session, email="consultora@example.com")
    await grant_room_app_role(db_session, user.id, "consultant")
    access, _refresh = await issue_tokens(db_session, user)
    return {"Authorization": f"Bearer {access}"}


@pytest.fixture()
async def session(db_session: AsyncSession) -> IRSession:
    language = await make_language(db_session, name="Lang a", code="la")
    project = await make_project(db_session, language.id, name="Team a")
    return await open_ir_session(db_session, pericope=P, project_id=project.id)


async def _coverage(
    client: httpx.AsyncClient, headers: dict[str, str], session_id: str
) -> dict[str, Any]:
    answer = await client.get(f"{IR}/facilitator/sessions/{session_id}/coverage", headers=headers)
    assert answer.status_code == 200, answer.text
    return answer.json()


def _labels(body: dict[str, Any]) -> dict[str, str]:
    return {bead["key"]: bead["label"] for group in body["groups"] for bead in group["beads"]}


async def test_the_beads_come_grouped_by_kind_in_her_order_each_with_the_maps_label(
    client: httpx.AsyncClient, consultant: dict[str, str], session: IRSession
) -> None:
    body = await _coverage(client, consultant, session.id)

    assert [group["kind"] for group in body["groups"]] == HER_KINDS
    labels = _labels(body)
    assert labels["arc"] == "Level-1 arc"
    assert labels["scene:1"] == "Famine and exile to Moab"
    assert labels["being:S1:B2"] == "Elimelech"
    assert labels["place:S1:PL1"] == "Bethlehem"


def _states(body: dict[str, Any]) -> dict[str, str]:
    return {bead["key"]: bead["state"] for group in body["groups"] for bead in group["beads"]}


async def test_each_bead_carries_one_of_her_three_states(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    db_session: AsyncSession,
) -> None:
    session.coverage_state = {"scene:1": "engaged", "being:S1:B3": "surfaced"}
    await db_session.commit()

    states = _states(await _coverage(client, consultant, session.id))

    assert states["scene:1"] == "engaged"
    assert states["being:S1:B3"] == "surfaced"
    assert states["being:S1:B2"] == "untouched"
    assert set(states.values()) == {"engaged", "surfaced", "untouched"}


async def test_a_bead_stored_at_the_retired_partial_state_reads_mentioned_and_no_old_word_appears(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    db_session: AsyncSession,
) -> None:
    session.coverage_state = {"scene:1": "partially_engaged", "scene:2": "engaged"}
    await db_session.commit()

    answer = await client.get(
        f"{IR}/facilitator/sessions/{session.id}/coverage", headers=consultant
    )

    assert answer.status_code == 200, answer.text
    assert _states(answer.json())["scene:1"] == "surfaced"
    for word in ("partially_engaged", "partial", "aflorado", "parcialmente", "not_encountered"):
        assert word not in answer.text
