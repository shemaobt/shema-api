"""Fixtures for the resource-request module's access tests.

The module has no routes of its own yet — BE-02 brings the tables and BE-03 the
capability checks — so the guards in ``_deps`` are exercised through a probe
router defined here. The handler returns nothing anybody reads: what is under
test is the dependency chain behind it, bearer token → ``get_current_user`` →
``require_app_access``, and the 403 it produces when a grant is missing.

Mounting a probe rather than the whole app keeps the module route-free until the
issue that is supposed to give it routes, and still exercises the real chain.
"""

from __future__ import annotations

import httpx
import pytest
from httpx import ASGITransport

from app.api.resource_requests._deps import APP_KEY
from tests.baker import make_app, make_role, make_user_app_role

PROBE = "/api/resource-requests/_probe"
MESA_PROBE = "/api/resource-requests/_probe/mesa"


@pytest.fixture(autouse=True)
def _clear_role_cache():
    """``require_app_access`` memoises roles for five minutes, keyed by user id.

    Harmless across tests (ids are uuids), fatal inside one: a call made before a
    grant caches the empty list and the grant then appears to do nothing. Clearing
    around every test means a test can check both sides of the same user.
    """
    from app.core.auth_cache import _roles_cache

    _roles_cache.clear()
    yield
    _roles_cache.clear()


@pytest.fixture()
async def rrf_app(db_session):
    """The app registry row plus its three roles — what ``seed_apps_roles.py`` writes."""
    app = await make_app(db_session, app_key=APP_KEY, name="Resource Request Form")

    for role_key, label in (("equipe", "Equipe"), ("mesa", "Mesa"), ("gestor", "Gestor")):
        await make_role(db_session, app.id, role_key=role_key, label=label, is_system=True)

    return app


@pytest.fixture()
async def client(db_session):
    """An ASGI client running the probe router and the real auth router.

    The real exception handlers are registered, so ``AuthorizationError`` reaches
    the wire as the 403 a client would actually receive.
    """
    from fastapi import APIRouter, FastAPI

    from app.api.auth import router as auth_router
    from app.api.resource_requests._deps import CurrentUser, MesaUser
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    probe = APIRouter()

    @probe.get("/_probe")
    async def _probe(user: CurrentUser) -> dict[str, str]:
        return {"email": user.email}

    @probe.get("/_probe/mesa")
    async def _probe_mesa(user: MesaUser) -> dict[str, str]:
        return {"email": user.email}

    test_app = FastAPI()
    test_app.include_router(probe, prefix="/api/resource-requests")
    test_app.include_router(auth_router, prefix="/api/auth")
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def auth_header(db_session, user) -> dict[str, str]:
    """A real bearer token for ``user``, decoded by the auth dependency."""
    from app.services.auth.issue_tokens import issue_tokens

    access, _refresh = await issue_tokens(db_session, user)
    return {"Authorization": f"Bearer {access}"}


async def grant(db_session, user, app, role_key: str):
    """Give ``user`` one of the app's already-seeded roles."""
    from sqlalchemy import select

    from app.db.models.auth import Role

    stmt = select(Role).where(Role.app_id == app.id, Role.role_key == role_key)
    role = (await db_session.execute(stmt)).scalar_one()
    return await make_user_app_role(db_session, user.id, app.id, role.id)
