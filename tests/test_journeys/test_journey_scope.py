"""A manager reads the journeys of the projects they command (OBT-507).

`console_guard` shut the catalog to non-operators, but every manager who passed
the door still got the whole catalog, while languages, projects and phases
already answer a manager with their own slice. A journey reaches a manager
through a project: the ones their projects were assigned are the ones they read.

The detail route is asserted too — a scoped list next to an open
`GET /journeys/{id}` would be a fence with no gate.

No positive case here uses a platform admin except the one that exists to prove
the admin path still returns everything, because the scope resolver returns
early for an admin.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport

from app.api.journeys import router as journeys_router
from app.core.auth_middleware import require_admin_or_manager
from app.core.database import get_db
from app.core.exceptions import register_exception_handlers
from app.db.models.org import MemberRole
from app.services.auth.issue_tokens import issue_tokens
from tests.baker import (
    make_journey,
    make_language,
    make_organization,
    make_organization_member,
    make_project,
    make_project_organization_access,
    make_project_user_access,
    make_user,
)


@pytest.fixture()
async def guarded_client(db_session):
    """Mounts the router exactly as `app.main` does — under `console_guard`."""
    test_app = FastAPI()
    test_app.include_router(
        journeys_router, prefix="/api/journeys", dependencies=[Depends(require_admin_or_manager)]
    )
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _headers(db_session, user) -> dict[str, str]:
    access, _refresh = await issue_tokens(db_session, user)
    return {"Authorization": f"Bearer {access}"}


async def _project_on_journey(db_session, code: str, journey_id: str | None = None):
    language = await make_language(db_session, code=code)
    return await make_project(db_session, language_id=language.id, journey_id=journey_id)


async def test_a_manager_lists_only_the_journeys_their_projects_carry(db_session, guarded_client):
    mine = await make_journey(db_session, name="Mine")
    theirs = await make_journey(db_session, name="Theirs")
    project = await _project_on_journey(db_session, "js1", mine.id)
    await _project_on_journey(db_session, "js2", theirs.id)
    manager = await make_user(db_session, email="projmgr@example.com")
    await make_project_user_access(
        db_session, project.id, manager.id, role=MemberRole.MANAGER.value
    )

    resp = await guarded_client.get("/api/journeys", headers=await _headers(db_session, manager))

    assert resp.status_code == 200
    assert [journey["name"] for journey in resp.json()] == ["Mine"]
    assert "Theirs" not in resp.text


async def test_a_manager_is_refused_a_journey_no_project_of_theirs_carries(
    db_session, guarded_client
):
    mine = await make_journey(db_session, name="Mine")
    theirs = await make_journey(db_session, name="Theirs")
    project = await _project_on_journey(db_session, "js3", mine.id)
    manager = await make_user(db_session, email="projmgr@example.com")
    await make_project_user_access(
        db_session, project.id, manager.id, role=MemberRole.MANAGER.value
    )

    resp = await guarded_client.get(
        f"/api/journeys/{theirs.id}", headers=await _headers(db_session, manager)
    )

    assert resp.status_code == 403
    assert "Theirs" not in resp.text


async def test_a_manager_may_open_a_journey_their_project_carries(db_session, guarded_client):
    mine = await make_journey(db_session, name="Mine")
    project = await _project_on_journey(db_session, "js4", mine.id)
    manager = await make_user(db_session, email="projmgr@example.com")
    await make_project_user_access(
        db_session, project.id, manager.id, role=MemberRole.MANAGER.value
    )

    resp = await guarded_client.get(
        f"/api/journeys/{mine.id}", headers=await _headers(db_session, manager)
    )

    assert resp.status_code == 200
    assert resp.json()["name"] == "Mine"


async def test_a_journey_reaches_the_manager_of_the_organization_holding_the_project(
    db_session, guarded_client
):
    mine = await make_journey(db_session, name="Mine")
    project = await _project_on_journey(db_session, "js5", mine.id)
    org = await make_organization(db_session, name="Org", slug="org-journeys")
    await make_project_organization_access(db_session, project.id, org.id)
    manager = await make_user(db_session, email="orgmgr@example.com")
    await make_organization_member(db_session, manager.id, org.id, role=MemberRole.MANAGER.value)

    resp = await guarded_client.get("/api/journeys", headers=await _headers(db_session, manager))

    assert resp.status_code == 200
    assert [journey["name"] for journey in resp.json()] == ["Mine"]


async def test_a_manager_whose_projects_carry_no_journey_lists_nothing(db_session, guarded_client):
    await make_journey(db_session, name="Theirs")
    project = await _project_on_journey(db_session, "js6")
    manager = await make_user(db_session, email="projmgr@example.com")
    await make_project_user_access(
        db_session, project.id, manager.id, role=MemberRole.MANAGER.value
    )

    resp = await guarded_client.get("/api/journeys", headers=await _headers(db_session, manager))

    assert resp.status_code == 200
    assert resp.json() == []


async def test_a_platform_admin_still_lists_every_journey(db_session, guarded_client):
    await make_journey(db_session, name="Mine")
    await make_journey(db_session, name="Theirs")
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)

    resp = await guarded_client.get("/api/journeys", headers=await _headers(db_session, admin))

    assert resp.status_code == 200
    assert sorted(journey["name"] for journey in resp.json()) == ["Mine", "Theirs"]


async def test_a_manager_asking_for_an_unknown_journey_is_refused_not_told_it_is_missing(
    db_session, guarded_client
):
    """The scope check runs before the lookup, so a scoped reader gets 403 where
    an admin gets 404. Deliberate: 404 would confirm which ids exist."""
    project = await _project_on_journey(db_session, "js7")
    manager = await make_user(db_session, email="projmgr@example.com")
    await make_project_user_access(
        db_session, project.id, manager.id, role=MemberRole.MANAGER.value
    )

    resp = await guarded_client.get(
        "/api/journeys/missing-id", headers=await _headers(db_session, manager)
    )

    assert resp.status_code == 403
