"""ENG-610 — a halted room nobody came back to leaves the facilitators' queue by the same
idle limit the session card already applies (`services/internalization_room/session_end.py`).

`sessions_waiting_on_a_person` used to list every `NEEDS_PERSON` row forever: the only two
doors out were a landing turn and a facilitator's own mark (ENG-609). A room the rest of the
system already calls `ABANDONED` still sent somebody walking to a conversation that ended.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import Role
from app.services.internalization_room import sessions as session_service
from app.services.internalization_room.canon.elements import element_keys
from app.services.internalization_room.coverage import CoverageStatus
from app.services.internalization_room.session_end import SESSION_IDLE_LIMIT
from tests.baker import make_app, make_role, make_user, make_user_app_role
from tests.test_facilitator_team_sessions_api import _ready_comprehension

APP_KEY = "internalization-room"
IR = "/api/internalization-room"
ROOM_KEY = "sala-de-teste"
P = "P03"
ENGAGED = CoverageStatus.ENGAGED.value


@pytest.fixture()
async def room_app(db_session: AsyncSession):
    app = await make_app(db_session, app_key=APP_KEY, name="Internalization Room")
    await make_role(db_session, app.id, role_key="facilitator", label="Facilitator", is_system=True)
    return app


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    from fastapi import FastAPI

    from app.api.internalization_room import router as room_router
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    monkeypatch.setattr(get_settings(), "internalization_room_api_key", ROOM_KEY, raising=False)

    test_app = FastAPI()
    test_app.include_router(room_router, prefix=IR)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


_TEAM = "Equipe da fila que drena"


async def _team(db_session: AsyncSession, name: str = _TEAM):
    """The team these sessions belong to, made once and found again by name."""
    from sqlalchemy import select

    from app.db.models.project import Project
    from tests.baker import make_language, make_project

    found = (
        await db_session.execute(select(Project).where(Project.name == name))
    ).scalar_one_or_none()
    if found is not None:
        return found
    language = await make_language(db_session, name=f"Lingua {name}", code=name[-3:].lower())
    return await make_project(db_session, language.id, name=name)


async def _a_session(db_session: AsyncSession, *, team=None, pericope: str = P):
    """A conversation belonging to a team, because one belonging to nobody reaches nobody."""
    team = team or await _team(db_session)
    return await session_service.create_session(db_session, pericope=pericope, project_id=team.id)


async def _facilitator(db_session: AsyncSession, room_app, team=None) -> dict[str, str]:
    from sqlalchemy import select

    from app.core.enums import ProjectRole
    from app.services.auth.issue_tokens import issue_tokens
    from tests.baker import make_project_user_access

    user = await make_user(db_session)
    role = (
        await db_session.execute(
            select(Role).where(Role.app_id == room_app.id, Role.role_key == "facilitator")
        )
    ).scalar_one()
    await make_user_app_role(db_session, user.id, room_app.id, role.id)
    team = team or await _team(db_session)
    await make_project_user_access(db_session, team.id, user.id, role=ProjectRole.FACILITATOR)
    access, _refresh = await issue_tokens(db_session, user)
    return {"Authorization": f"Bearer {access}"}


async def _halt(client: httpx.AsyncClient, session_id: str) -> None:
    """The way the room actually halts: the tablet says it cannot go on without a person."""
    asked = await client.post(
        f"{IR}/sessions/{session_id}/needs-person", headers={"X-Room-Key": ROOM_KEY}
    )
    assert asked.status_code == 200, asked.text[:200]


@pytest.mark.asyncio
async def test_an_old_halt_leaves_and_a_fresh_one_stays_in_the_same_read(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app
) -> None:
    team = await _team(db_session)
    old = await _a_session(db_session, team=team)
    fresh = await _a_session(db_session, team=team)
    await _halt(client, old.id)
    await _halt(client, fresh.id)
    old.updated_at = datetime.now(UTC) - SESSION_IDLE_LIMIT - timedelta(minutes=1)
    await db_session.commit()
    headers = await _facilitator(db_session, room_app, team=team)

    listed = await client.get(f"{IR}/facilitator/sessions", headers=headers)

    assert listed.status_code == 200, listed.text[:300]
    shown = {row["session_id"] for row in listed.json()["sessions"]}
    assert fresh.id in shown, "a sala ainda dentro do limite sumiu da fila"
    assert old.id not in shown, "a sala parada e ociosa além do limite ainda aparece na fila"


@pytest.mark.asyncio
async def test_the_done_half_is_untouched(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app
) -> None:
    team = await _team(db_session)
    session = await session_service.create_session(
        db_session, pericope=P, project_id=team.id, bridge_mode="guided_microchecks"
    )
    session = await session_service.save_comprehension(db_session, session, _ready_comprehension(P))
    session = await session_service.apply_coverage(
        db_session, session.id, dict.fromkeys(element_keys(P), ENGAGED)
    )
    assert session.status.value == "done", "a sessão precisa terminar para o caso valer algo"
    session.updated_at = datetime.now(UTC) - SESSION_IDLE_LIMIT - timedelta(minutes=1)
    await db_session.commit()
    headers = await _facilitator(db_session, room_app, team=team)

    listed = await client.get(f"{IR}/facilitator/sessions", headers=headers)

    assert listed.status_code == 200, listed.text[:300]
    shown = {row["session_id"] for row in listed.json()["sessions"]}
    assert session.id in shown, "a metade DONE não drena pelo limite de ociosidade e não pode sumir"


@pytest.mark.asyncio
async def test_the_limit_is_end_ofs_own_not_a_copy(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app
) -> None:
    team = await _team(db_session)
    inside = await _a_session(db_session, team=team)
    outside = await _a_session(db_session, team=team)
    await _halt(client, inside.id)
    await _halt(client, outside.id)
    now = datetime.now(UTC)
    inside.updated_at = now - SESSION_IDLE_LIMIT + timedelta(minutes=1)
    outside.updated_at = now - SESSION_IDLE_LIMIT - timedelta(minutes=1)
    await db_session.commit()
    headers = await _facilitator(db_session, room_app, team=team)

    listed = await client.get(f"{IR}/facilitator/sessions", headers=headers)

    assert listed.status_code == 200, listed.text[:300]
    shown = {row["session_id"] for row in listed.json()["sessions"]}
    assert inside.id in shown, "um minuto dentro do limite já não aparece"
    assert outside.id not in shown, "um minuto além do limite ainda aparece"
