from __future__ import annotations

import httpx
import pytest
from httpx import ASGITransport

from app.core.rate_limit import limiter


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Limiter storage is global and in-process: without a reset, a test leaks into the next."""
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture()
async def client(db_session):
    """ASGI client mounting ONLY the platform router.

    Runs the REAL auth chain (`get_current_user`) — that is what needs proving: the platform
    has no app key, so the endpoint serves any authenticated user from any app, and an
    anonymous caller has to be turned away.
    """
    from fastapi import FastAPI
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded

    from app.api.platform import router as platform_router
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    test_app = FastAPI()
    test_app.state.limiter = limiter
    test_app.include_router(platform_router, prefix="/api/platform")
    register_exception_handlers(test_app)
    test_app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def auth_header(db_session, user) -> dict[str, str]:
    """A real bearer token for `user` (decoded by the auth dependency)."""
    from app.services.auth.issue_tokens import issue_tokens

    access, _refresh = await issue_tokens(db_session, user)
    return {"Authorization": f"Bearer {access}"}
