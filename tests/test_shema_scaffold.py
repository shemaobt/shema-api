from __future__ import annotations

import httpx
import pytest
from httpx import ASGITransport
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import Settings
from app.core.version import FALLBACK_VERSION, get_app_version
from app.services.shema import MODULE_NAME, get_module_status

SHEMA = "/api/shema"


@pytest.fixture()
async def client(db_session):
    from fastapi import FastAPI

    from app.api.health import router as health_router
    from app.api.shema import router as shema_router
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    test_app = FastAPI(title="Tripod Backend", version=get_app_version())
    test_app.include_router(health_router)
    test_app.include_router(shema_router, prefix=SHEMA, tags=["shema"])
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_health_returns_ok_with_a_version(client):
    response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"]


@pytest.mark.asyncio
async def test_app_version_resolves_from_the_installed_distribution():
    assert get_app_version() != FALLBACK_VERSION


@pytest.mark.asyncio
async def test_shema_health_reports_the_module_and_its_database(client):
    response = await client.get(f"{SHEMA}/health")

    assert response.status_code == 200
    assert response.json() == {
        "module": MODULE_NAME,
        "status": "ok",
        "version": get_app_version(),
        "database": "ok",
    }


@pytest.mark.asyncio
async def test_shema_health_degrades_when_the_database_is_unreachable():
    class _UnreachableSession:
        async def execute(self, *_args, **_kwargs):
            raise SQLAlchemyError("connection refused")

    status = await get_module_status(_UnreachableSession())

    assert status.database == "unavailable"
    assert status.status == "degraded"


@pytest.mark.asyncio
async def test_openapi_documents_the_shema_module(client):
    schema = (await client.get("/openapi.json")).json()

    assert f"{SHEMA}/health" in schema["paths"]
    assert schema["paths"][f"{SHEMA}/health"]["get"]["tags"] == ["shema"]


def test_settings_reject_a_missing_required_value(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)

    with pytest.raises(ValidationError, match=r"(?i)jwt_secret_key"):
        Settings(_env_file=None)


def test_settings_reject_a_blank_required_value(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
    monkeypatch.setenv("JWT_SECRET_KEY", "   ")

    with pytest.raises(ValidationError, match=r"(?i)jwt_secret_key"):
        Settings(_env_file=None)
