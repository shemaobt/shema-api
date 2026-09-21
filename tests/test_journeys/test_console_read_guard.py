"""The journey and phase-category *reads* are Console-only (OBT-506).

Before this, both lists were mounted with no guard, so any authenticated
account — including a user of an ecosystem app with no Console role — could
read the journey/phase-category catalog. They now sit behind `console_guard`
(`require_admin_or_manager`), exactly like `languages` and `phases` do once
#93 lands. Writes stay platform-admin-only and are covered elsewhere.

Every positive case here uses a *non-admin* manager (an org manager and a
project manager), and the negative case a role-less user, because
`require_admin_or_manager` returns early for a platform admin: a gate proven
only with an admin account would keep passing after the gate was removed.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport

from app.api.journeys import router as journeys_router
from app.api.phase_categories import router as phase_categories_router
from app.core.auth_middleware import require_admin_or_manager
from app.core.database import get_db
from app.core.exceptions import register_exception_handlers
from app.db.models.org import MemberRole
from app.services.auth.issue_tokens import issue_tokens
from tests.baker import (
    make_language,
    make_organization,
    make_organization_member,
    make_project,
    make_project_user_access,
    make_user,
)

READS = ["/api/journeys", "/api/phase-categories"]


@pytest.fixture()
async def guarded_client(db_session):
    """Mounts the two routers exactly as `app.main` does — under `console_guard`."""
    console_guard = [Depends(require_admin_or_manager)]
    test_app = FastAPI()
    test_app.include_router(journeys_router, prefix="/api/journeys", dependencies=console_guard)
    test_app.include_router(
        phase_categories_router, prefix="/api/phase-categories", dependencies=console_guard
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


@pytest.mark.parametrize("path", READS)
async def test_role_less_user_is_denied(db_session, guarded_client, path):
    user = await make_user(db_session, email="nobody@example.com")
    headers = await _headers(db_session, user)

    resp = await guarded_client.get(path, headers=headers)

    assert resp.status_code == 403


@pytest.mark.parametrize("path", READS)
async def test_org_manager_may_read(db_session, guarded_client, path):
    manager = await make_user(db_session, email="orgmgr@example.com")
    org = await make_organization(db_session, name="Org", slug="org")
    await make_organization_member(db_session, manager.id, org.id, role=MemberRole.MANAGER.value)
    headers = await _headers(db_session, manager)

    resp = await guarded_client.get(path, headers=headers)

    assert resp.status_code == 200


@pytest.mark.parametrize("path", READS)
async def test_project_manager_may_read(db_session, guarded_client, path):
    manager = await make_user(db_session, email="projmgr@example.com")
    lang = await make_language(db_session, code="jgd")
    project = await make_project(db_session, language_id=lang.id)
    await make_project_user_access(
        db_session, project.id, manager.id, role=MemberRole.MANAGER.value
    )
    headers = await _headers(db_session, manager)

    resp = await guarded_client.get(path, headers=headers)

    assert resp.status_code == 200


@pytest.mark.parametrize("path", READS)
async def test_platform_admin_may_read(db_session, guarded_client, path):
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    headers = await _headers(db_session, admin)

    resp = await guarded_client.get(path, headers=headers)

    assert resp.status_code == 200
