"""Console read endpoints are not readable by accounts without a console role.

These are the gates added for OBT-506. Every negative case here uses a
*non-admin* account on purpose: `require_platform_admin` and every role guard
return early for a platform admin, so a per-role gate "proven" with an admin
account passes for the wrong reason and would keep passing after the guard was
deleted. The user directory search is verified through its query-length floor
rather than a role gate, because the pick-a-user flows legitimately call it.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport

from app.api.roles import router as roles_router
from app.api.users import router as users_router
from app.core.database import get_db
from app.core.exceptions import register_exception_handlers
from app.services.auth.issue_tokens import issue_tokens
from tests.baker import make_app, make_role, make_user, make_user_app_role


@pytest.fixture()
async def client(db_session):
    test_app = FastAPI()
    test_app.include_router(users_router, prefix="/api/users")
    test_app.include_router(roles_router, prefix="/api/roles")
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


# --- users/{id} and users/{id}/roles: platform admin only (findings #2) ---


async def test_get_user_is_denied_to_a_non_admin(db_session, client) -> None:
    caller = await make_user(db_session, email="plain@example.com")
    target = await make_user(db_session, email="target@example.com")
    headers = await _headers(db_session, caller)

    response = await client.get(f"/api/users/{target.id}", headers=headers)

    assert response.status_code == 403


async def test_get_user_is_allowed_for_a_platform_admin(db_session, client) -> None:
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    target = await make_user(db_session, email="seen@example.com")
    headers = await _headers(db_session, admin)

    response = await client.get(f"/api/users/{target.id}", headers=headers)

    assert response.status_code == 200
    assert response.json()["email"] == "seen@example.com"


async def test_list_user_roles_is_denied_to_a_non_admin(db_session, client) -> None:
    caller = await make_user(db_session, email="plain2@example.com")
    target = await make_user(db_session, email="target2@example.com")
    headers = await _headers(db_session, caller)

    response = await client.get(f"/api/users/{target.id}/roles", headers=headers)

    assert response.status_code == 403


async def test_list_user_roles_is_allowed_for_a_platform_admin(db_session, client) -> None:
    admin = await make_user(db_session, email="admin2@example.com", is_platform_admin=True)
    target = await make_user(db_session, email="target3@example.com")
    headers = await _headers(db_session, admin)

    response = await client.get(f"/api/users/{target.id}/roles", headers=headers)

    assert response.status_code == 200
    assert response.json() == []


# --- users/search: query-length floor stops directory enumeration (finding #1) ---


async def test_search_with_empty_query_returns_no_one(db_session, client) -> None:
    caller = await make_user(db_session, email="searcher@example.com")
    await make_user(db_session, email="alice@example.com", display_name="Alice")
    await make_user(db_session, email="bob@example.com", display_name="Bob")
    headers = await _headers(db_session, caller)

    response = await client.get("/api/users/search", headers=headers)

    assert response.status_code == 200
    assert response.json() == [], "an empty query must not dump the directory"


async def test_search_with_one_character_returns_no_one(db_session, client) -> None:
    caller = await make_user(db_session, email="searcher2@example.com")
    await make_user(db_session, email="alice2@example.com", display_name="Alice")
    headers = await _headers(db_session, caller)

    response = await client.get("/api/users/search", params={"q": "a"}, headers=headers)

    assert response.status_code == 200
    assert response.json() == []


async def test_search_with_a_real_query_still_finds_matches(db_session, client) -> None:
    caller = await make_user(db_session, email="searcher3@example.com")
    await make_user(db_session, email="zephyr@example.com", display_name="Zephyr")
    headers = await _headers(db_session, caller)

    response = await client.get("/api/users/search", params={"q": "zephyr"}, headers=headers)

    assert response.status_code == 200
    emails = [u["email"] for u in response.json()]
    assert "zephyr@example.com" in emails


# --- roles/check: self allowed, probing others needs role-management authority (finding #4) ---


async def test_check_own_role_is_allowed_for_any_account(db_session, client) -> None:
    caller = await make_user(db_session, email="self@example.com")
    headers = await _headers(db_session, caller)

    response = await client.get(
        "/api/roles/check",
        params={"user_id": caller.id, "app_key": "oral-collector", "role_key": "admin"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json() == {"allowed": False}


async def test_check_other_users_role_is_denied_to_a_non_admin(db_session, client) -> None:
    caller = await make_user(db_session, email="prober@example.com")
    target = await make_user(db_session, email="victim@example.com")
    headers = await _headers(db_session, caller)

    response = await client.get(
        "/api/roles/check",
        params={"user_id": target.id, "app_key": "oral-collector", "role_key": "admin"},
        headers=headers,
    )

    # assert_can_manage_roles raises RoleError, which the app maps to 400
    assert response.status_code == 400


async def test_check_other_users_role_is_allowed_for_a_platform_admin(db_session, client) -> None:
    admin = await make_user(db_session, email="admin3@example.com", is_platform_admin=True)
    target = await make_user(db_session, email="probed@example.com")
    headers = await _headers(db_session, admin)

    response = await client.get(
        "/api/roles/check",
        params={"user_id": target.id, "app_key": "oral-collector", "role_key": "admin"},
        headers=headers,
    )

    assert response.status_code == 200
    assert "allowed" in response.json()


async def test_check_other_users_role_is_allowed_for_an_app_admin(db_session, client) -> None:
    app = await make_app(db_session, app_key="oral-collector", name="Oral Collector")
    admin_role = await make_role(db_session, app.id, role_key="admin", label="Admin")
    caller = await make_user(db_session, email="appadmin@example.com")
    await make_user_app_role(db_session, caller.id, app.id, admin_role.id)
    target = await make_user(db_session, email="probed2@example.com")
    headers = await _headers(db_session, caller)

    response = await client.get(
        "/api/roles/check",
        params={"user_id": target.id, "app_key": "oral-collector", "role_key": "admin"},
        headers=headers,
    )

    assert response.status_code == 200
    assert "allowed" in response.json()
