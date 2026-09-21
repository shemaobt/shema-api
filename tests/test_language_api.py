import httpx
import pytest
from httpx import ASGITransport

from app.services import language_service
from app.services.auth.issue_tokens import issue_tokens
from tests.baker import make_language, make_user


@pytest.fixture()
async def client(db_session):
    from fastapi import FastAPI

    from app.api.languages import router as languages_router
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    test_app = FastAPI()
    test_app.include_router(languages_router, prefix="/api/languages")
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _auth_header(db_session, user) -> dict[str, str]:
    access, _refresh = await issue_tokens(db_session, user)
    return {"Authorization": f"Bearer {access}"}


@pytest.mark.asyncio
async def test_reactivate_endpoint_admin_returns_active_language(client, db_session) -> None:
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    language = await make_language(db_session, code="kos")
    await language_service.deactivate_language(db_session, language.id, admin)

    headers = await _auth_header(db_session, admin)
    response = await client.post(f"/api/languages/{language.id}/reactivate", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(language.id)
    assert body["is_active"] is True


@pytest.mark.asyncio
async def test_reactivate_endpoint_forbidden_for_non_admin(client, db_session) -> None:
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    manager = await make_user(db_session, email="manager@example.com")
    language = await make_language(db_session, code="kos")
    await language_service.deactivate_language(db_session, language.id, admin)

    headers = await _auth_header(db_session, manager)
    response = await client.post(f"/api/languages/{language.id}/reactivate", headers=headers)

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_reactivate_endpoint_missing_returns_404(client, db_session) -> None:
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    headers = await _auth_header(db_session, admin)
    response = await client.post(
        "/api/languages/00000000-0000-0000-0000-000000000000/reactivate", headers=headers
    )

    assert response.status_code == 404
