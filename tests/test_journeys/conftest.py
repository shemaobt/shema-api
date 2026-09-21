from __future__ import annotations

import httpx
import pytest
from httpx import ASGITransport


@pytest.fixture()
async def client(db_session):
    from fastapi import FastAPI

    from app.api.journeys import router as journeys_router
    from app.api.phase_categories import router as phase_categories_router
    from app.api.phases import router as phases_router
    from app.api.projects import router as projects_router
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    test_app = FastAPI()
    test_app.include_router(journeys_router, prefix="/api/journeys")
    test_app.include_router(phase_categories_router, prefix="/api/phase-categories")
    test_app.include_router(phases_router, prefix="/api/phases")
    test_app.include_router(projects_router, prefix="/api/projects")
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def auth_header(db_session, user) -> dict[str, str]:
    from app.services.auth.issue_tokens import issue_tokens

    access, _refresh = await issue_tokens(db_session, user)
    return {"Authorization": f"Bearer {access}"}
