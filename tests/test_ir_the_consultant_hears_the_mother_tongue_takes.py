"""ENG-1334 — the consultant reads the mother-tongue takes of a session, with her facts per take.

Every case drives the real application through the door the Desk reads by.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession
from app.db.models.project import Project
from tests.baker import (
    grant_room_app_role,
    make_language,
    make_project,
    make_user,
    open_ir_session,
)
from tests.release_harness import ensaio_take

IR = "/api/internalization-room"
P = "P01"


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
async def team(db_session: AsyncSession) -> Project:
    language = await make_language(db_session, name="Lang a", code="la")
    return await make_project(db_session, language.id, name="Team a")


@pytest.fixture()
async def session(db_session: AsyncSession, team: Project) -> IRSession:
    return await open_ir_session(db_session, pericope=P, project_id=team.id)


async def _keep(
    db: AsyncSession, session: IRSession, team: Project, *, ordinal: int | None, sha: str
) -> str:
    take = ensaio_take(session.id, ordinal=ordinal, sha256=sha, project_id=team.id)
    db.add(take)
    await db.commit()
    return take.id


async def _read(
    client: httpx.AsyncClient, headers: dict[str, str], session_id: str
) -> dict[str, Any]:
    answer = await client.get(
        f"{IR}/facilitator/sessions/{session_id}/mother-tongue-takes", headers=headers
    )
    assert answer.status_code == 200, answer.text
    return answer.json()


async def test_the_takes_come_in_reading_order_each_named_by_its_position_among_the_parts(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    team: Project,
    db_session: AsyncSession,
) -> None:
    third = await _keep(db_session, session, team, ordinal=3, sha="c" * 64)
    first = await _keep(db_session, session, team, ordinal=1, sha="a" * 64)
    second = await _keep(db_session, session, team, ordinal=2, sha="b" * 64)

    body = await _read(client, consultant, session.id)

    assert [(row["take_id"], row["part"]) for row in body["takes"]] == [
        (first, 1),
        (second, 2),
        (third, 3),
    ]


async def test_a_rehearsal_told_whole_has_no_part_and_does_not_move_the_numbered_ones(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    team: Project,
    db_session: AsyncSession,
) -> None:
    first = await _keep(db_session, session, team, ordinal=1, sha="a" * 64)
    whole = await _keep(db_session, session, team, ordinal=None, sha="w" * 64)
    second = await _keep(db_session, session, team, ordinal=2, sha="b" * 64)

    body = await _read(client, consultant, session.id)

    assert [(row["take_id"], row["part"]) for row in body["takes"]] == [
        (whole, None),
        (first, 1),
        (second, 2),
    ]
