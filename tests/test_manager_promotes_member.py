"""A project manager promotes a member to manager, and only a platform admin undoes it.

Product rule of 2026-10-01: the console offers the manager the *Manager* option on a
member's row and in the grant dialog. What the manager cannot do is touch a manager row
afterwards, the one just promoted included. These tests pin that contract at the HTTP
boundary, since that is where the console meets it.
"""

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from tests.baker import make_language, make_project, make_project_user_access, make_user


@pytest.fixture()
async def client(db_session: AsyncSession):
    from app.core.database import get_db
    from app.main import app

    async def _get_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


async def _headers(db_session: AsyncSession, user) -> dict[str, str]:
    from app.services.auth.issue_tokens import issue_tokens

    access, _refresh = await issue_tokens(db_session, user)
    return {"Authorization": f"Bearer {access}"}


async def _team(db_session: AsyncSession):
    lang = await make_language(db_session, code="pmm")
    project = await make_project(db_session, language_id=lang.id)
    manager = await make_user(db_session, email="manager@promote.com")
    member = await make_user(db_session, email="member@promote.com")
    await make_project_user_access(db_session, project.id, manager.id, role="manager")
    await make_project_user_access(db_session, project.id, member.id, role="member")
    return project, manager, member


async def test_manager_promotes_a_member_and_cannot_undo_it(client, db_session) -> None:
    project, manager, member = await _team(db_session)
    headers = await _headers(db_session, manager)
    row = f"/api/projects/{project.id}/access/users/{member.id}"

    promoted = await client.patch(row, json={"role": "manager"}, headers=headers)
    assert promoted.status_code == 200, promoted.text
    assert promoted.json()["role"] == "manager"

    demote = await client.patch(row, json={"role": "member"}, headers=headers)
    revoke = await client.delete(row, headers=headers)
    assert demote.status_code == 403
    assert revoke.status_code == 403


async def test_manager_grants_access_directly_as_manager(client, db_session) -> None:
    project, manager, _member = await _team(db_session)
    newcomer = await make_user(db_session, email="newcomer@promote.com")
    headers = await _headers(db_session, manager)

    granted = await client.post(
        f"/api/projects/{project.id}/access/users",
        json={"user_id": newcomer.id, "role": "manager"},
        headers=headers,
    )

    assert granted.status_code == 201, granted.text
    assert granted.json()["role"] == "manager"


async def test_platform_admin_undoes_a_promotion(client, db_session) -> None:
    project, manager, member = await _team(db_session)
    admin = await make_user(db_session, email="admin@promote.com", is_platform_admin=True)
    row = f"/api/projects/{project.id}/access/users/{member.id}"
    await client.patch(row, json={"role": "manager"}, headers=await _headers(db_session, manager))

    admin_headers = await _headers(db_session, admin)
    demoted = await client.patch(row, json={"role": "member"}, headers=admin_headers)
    revoked = await client.delete(row, headers=admin_headers)

    assert demoted.status_code == 200
    assert demoted.json()["role"] == "member"
    assert revoked.status_code == 204
