from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport

from app.api.users import router as users_router
from app.core.database import get_db
from app.core.exceptions import register_exception_handlers
from app.services.auth.issue_tokens import issue_tokens
from tests.baker import make_user


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


async def _admin_header(db_session) -> dict[str, str]:
    admin = await make_user(db_session, email="admin-api@example.com", is_platform_admin=True)
    access, _refresh = await issue_tokens(db_session, admin)
    return {"Authorization": f"Bearer {access}"}


async def test_patch_with_null_avatar_removes_the_photo(db_session, client) -> None:
    headers = await _admin_header(db_session)
    target = await make_user(db_session, email="target@example.com")
    target.avatar_url = "https://x/a.png"
    await db_session.commit()

    response = await client.patch(
        f"/api/users/{target.id}", json={"avatar_url": None}, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["avatar_url"] is None


async def test_patch_without_avatar_field_keeps_the_photo(db_session, client) -> None:
    headers = await _admin_header(db_session)
    target = await make_user(db_session, email="keep@example.com")
    target.avatar_url = "https://x/a.png"
    await db_session.commit()

    response = await client.patch(
        f"/api/users/{target.id}", json={"is_active": False}, headers=headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["avatar_url"] == "https://x/a.png"
    assert body["is_active"] is False
