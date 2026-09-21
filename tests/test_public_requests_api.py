import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import public_request_service
from tests.baker import make_user


@pytest.fixture()
async def client(db_session: AsyncSession):
    from fastapi import FastAPI

    from app.api.public_requests import router
    from app.core.auth_middleware import require_platform_admin
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    test_app = FastAPI()
    test_app.include_router(router, prefix="/api/public-requests")
    register_exception_handlers(test_app)

    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    test_app.dependency_overrides[require_platform_admin] = lambda: admin
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def a_language_request(db: AsyncSession):
    return await public_request_service.create_language_request(
        db,
        requester_name="Ana Silva",
        requester_email="ana@example.com",
        name="Arara",
        code="ara",
    )


async def test_list_refuses_a_status_outside_the_machine(client):
    response = await client.get("/api/public-requests", params={"status": "bogus"})
    assert response.status_code == 422


async def test_list_refuses_a_kind_outside_the_machine(client):
    response = await client.get("/api/public-requests", params={"kind": "create_planet"})
    assert response.status_code == 422


async def test_list_filters_by_a_status_the_machine_holds(client, db_session):
    request = await a_language_request(db_session)

    pending = await client.get("/api/public-requests", params={"status": "pending"})
    assert pending.status_code == 200
    assert [item["id"] for item in pending.json()] == [request.id]

    approved = await client.get("/api/public-requests", params={"status": "approved"})
    assert approved.status_code == 200
    assert approved.json() == []


async def test_review_refuses_pending_as_a_verdict(client, db_session):
    request = await a_language_request(db_session)

    response = await client.patch(
        f"/api/public-requests/{request.id}/review", json={"status": "pending"}
    )
    assert response.status_code == 422


async def test_review_approves_with_a_verdict_the_machine_holds(client, db_session):
    request = await a_language_request(db_session)

    response = await client.patch(
        f"/api/public-requests/{request.id}/review", json={"status": "approved"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    assert response.json()["created_entity_id"] is not None
