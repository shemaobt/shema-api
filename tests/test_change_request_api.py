import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from tests.baker import make_user

CHANGE_REQUESTS_URL = "/api/change-requests"


@pytest.fixture()
async def client(db_session: AsyncSession):
    from fastapi import FastAPI

    from app.api.change_requests import router
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    test_app = FastAPI()
    test_app.include_router(router, prefix=CHANGE_REQUESTS_URL)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def an_admin(db: AsyncSession) -> dict[str, str]:
    from app.services.auth.issue_tokens import issue_tokens

    user = await make_user(db, email="admin@example.com", is_platform_admin=True)
    access, _refresh = await issue_tokens(db, user)
    return {"Authorization": f"Bearer {access}"}


@pytest.mark.asyncio
async def test_list_refuses_a_misspelled_status(client, db_session) -> None:
    headers = await an_admin(db_session)
    response = await client.get(CHANGE_REQUESTS_URL, params={"status": "aproved"}, headers=headers)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_refuses_a_misspelled_kind(client, db_session) -> None:
    headers = await an_admin(db_session)
    response = await client.get(
        CHANGE_REQUESTS_URL, params={"kind": "create_projects"}, headers=headers
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_accepts_the_known_filters(client, db_session) -> None:
    headers = await an_admin(db_session)
    response = await client.get(
        CHANGE_REQUESTS_URL,
        params={"kind": "create_language", "status": "pending"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json() == []
