"""The user directory is searchable by Console operators only (OBT-507).

`GET /api/users/search` depended on `get_current_user` alone, so any account
that could log in — including a user of an ecosystem app with no Console role —
could read the directory: email, display name and the `is_platform_admin` flag,
fifty rows at a time. That is not privilege escalation, it is a target list, and
the login it feeds has no attempt lockout. The search now sits behind the same
`require_admin_or_manager` the rest of the Console reads use.

The positive cases use a *non-admin* manager and the negative cases a member and
a role-less account, because the guard returns early for a platform admin: a
gate proven only with an admin account keeps passing after the gate is deleted.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport

from app.api.users import router as users_router
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

SEARCH = "/api/users/search?q=findable"


@pytest.fixture()
async def client(db_session):
    test_app = FastAPI()
    test_app.include_router(users_router, prefix="/api/users")
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


async def _a_findable_account(db_session):
    return await make_user(db_session, email="findable@example.com", display_name="Findable")


async def test_a_role_less_account_is_refused_the_directory(db_session, client):
    await _a_findable_account(db_session)
    nobody = await make_user(db_session, email="nobody@example.com")

    resp = await client.get(SEARCH, headers=await _headers(db_session, nobody))

    assert resp.status_code == 403
    assert "findable@example.com" not in resp.text


async def test_a_project_member_is_refused_the_directory(db_session, client):
    await _a_findable_account(db_session)
    member = await make_user(db_session, email="member@example.com")
    language = await make_language(db_session, code="mbr")
    project = await make_project(db_session, language_id=language.id)
    await make_project_user_access(db_session, project.id, member.id, role=MemberRole.MEMBER.value)

    resp = await client.get(SEARCH, headers=await _headers(db_session, member))

    assert resp.status_code == 403
    assert "findable@example.com" not in resp.text


async def test_a_project_manager_may_search_the_directory(db_session, client):
    await _a_findable_account(db_session)
    manager = await make_user(db_session, email="projmgr@example.com")
    language = await make_language(db_session, code="pjm")
    project = await make_project(db_session, language_id=language.id)
    await make_project_user_access(
        db_session, project.id, manager.id, role=MemberRole.MANAGER.value
    )

    resp = await client.get(SEARCH, headers=await _headers(db_session, manager))

    assert resp.status_code == 200
    assert [row["email"] for row in resp.json()] == ["findable@example.com"]


async def test_an_organization_manager_may_search_the_directory(db_session, client):
    await _a_findable_account(db_session)
    manager = await make_user(db_session, email="orgmgr@example.com")
    org = await make_organization(db_session, name="Org", slug="org-search")
    await make_organization_member(db_session, manager.id, org.id, role=MemberRole.MANAGER.value)

    resp = await client.get(SEARCH, headers=await _headers(db_session, manager))

    assert resp.status_code == 200


async def test_a_platform_admin_may_search_the_directory(db_session, client):
    await _a_findable_account(db_session)
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)

    resp = await client.get(SEARCH, headers=await _headers(db_session, admin))

    assert resp.status_code == 200
