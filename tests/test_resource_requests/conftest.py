"""Fixtures for the resource-request module's access tests.

The module has no routes of its own yet — BE-04 onwards brings them — so the guards in
``_deps`` are exercised through a probe router defined here. The handler returns nothing
anybody reads: what is under test is the dependency chain behind it, bearer token →
``get_current_user`` → ``require_app_access`` → ``require_capability``, and the 403 each
link produces.

Mounting a probe rather than the whole app keeps the module route-free until the issue
that is supposed to give it routes, and still exercises the real chain.

**The nine capability probes hang off the named aliases, not off
``require_capability("…")`` rebuilt here.** Those aliases are what BE-04 onwards will
annotate a route with, so an alias wired to the wrong capability is a real defect, and a
probe that built its own dependency would test the factory while leaving the wiring
unread. ``test_capabilities.py`` asserts that every capability in the map has a probe, so
the nine cannot quietly become eight.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from httpx import ASGITransport

from app.api.resource_requests._deps import (
    APP_KEY,
    CanAdministerFunds,
    CanAllocateFunds,
    CanAssignFund,
    CanEditEvaluation,
    CanEditRequests,
    CanEndorseRequest,
    CanManageFunds,
    CanMoveBoard,
    CanViewEvaluation,
    CurrentUser,
    MesaUser,
)
from app.services.resource_request import CAPABILITIES
from tests.baker import make_app, make_role, make_user_app_role

PROBE = "/api/resource-requests/_probe"
MESA_PROBE = "/api/resource-requests/_probe/mesa"

#: One probe per capability, keyed by the capability it guards on.
CAP_PROBES: dict[str, str] = {
    capability: f"{PROBE}/cap/{capability}" for capability in CAPABILITIES
}

#: The vendored emission, read once. `docs/capabilities.json` of
#: `shemaobt/resource-request-form`, copied byte for byte and carrying the frontend commit
#: it came from. Read here rather than in each test module so the path is stated once and
#: the seed check and the mirror check are looking at the same file.
EMISSION: dict = json.loads(
    (
        Path(__file__).resolve().parents[2]
        / "app"
        / "services"
        / "resource_request"
        / "capabilities.json"
    ).read_text(encoding="utf-8")
)

#: The role ids the frontend actually ships, from that emission.
FRONTEND_ROLE_IDS: list[str] = [role["id"] for role in EMISSION["roles"]]


@pytest.fixture(autouse=True)
def _clear_role_cache():
    """``require_app_access`` memoises roles for ``AUTH_CACHE_TTL_SECONDS``, by user id.

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
    """The app registry row plus its four roles — what ``seed_apps_roles.py`` writes.

    ``auto_approve`` is on because ``20260828_rr02`` turns it on: GATE-02 D1 answered that
    whoever registers gets in, as ``equipe``. The fixture carries the row production has,
    not the row the seed script leaves behind.
    """
    app = await make_app(
        db_session, app_key=APP_KEY, name="Resource Request Form", auto_approve=True
    )

    for role_key, label in (
        ("equipe", "Equipe"),
        ("mesa", "Mesa"),
        ("gestor", "Gestor"),
        ("lider", "Líder de Base"),
    ):
        await make_role(db_session, app.id, role_key=role_key, label=label, is_system=True)

    return app


@pytest.fixture()
async def client(db_session):
    """An ASGI client running the probe router, the module's own router and auth.

    The module router is mounted at the same prefix the application mounts it at, so the
    lifecycle tests exercise the real paths — ``/api/resource-requests/requests`` — through
    the real dependency chain. The probes keep their own ``/_probe`` space beside it: they
    test the guards where no route needs to exist, and they outlive any particular route.

    The real exception handlers are registered, so ``AuthorizationError`` reaches the
    wire as the 403 a client would actually receive.

    ``CurrentUser`` and ``MesaUser`` are imported at module level on purpose. These
    handlers are defined inside this fixture, so their ``__globals__`` is this module —
    and with ``from __future__ import annotations`` every annotation is a string FastAPI
    resolves against exactly that namespace. Bound locally instead, the name does not
    resolve, FastAPI falls back to treating ``user`` as a required query parameter, and
    every guarded call answers 422 before the guard ever runs.
    """
    from fastapi import APIRouter, FastAPI

    from app.api.auth import router as auth_router
    from app.api.resource_requests import router as module_router
    from app.api.resource_requests.access import router as access_router
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    probe = APIRouter()

    @probe.get("/_probe")
    async def _probe(user: CurrentUser) -> dict[str, str]:
        return {"email": user.email}

    @probe.get("/_probe/mesa")
    async def _probe_mesa(user: MesaUser) -> dict[str, str]:
        return {"email": user.email}

    @probe.get("/_probe/cap/edit_requests")
    async def _probe_edit_requests(user: CanEditRequests) -> dict[str, str]:
        return {"email": user.email}

    @probe.get("/_probe/cap/view_evaluation")
    async def _probe_view_evaluation(user: CanViewEvaluation) -> dict[str, str]:
        return {"email": user.email}

    @probe.get("/_probe/cap/edit_evaluation")
    async def _probe_edit_evaluation(user: CanEditEvaluation) -> dict[str, str]:
        return {"email": user.email}

    @probe.get("/_probe/cap/manage_funds")
    async def _probe_manage_funds(user: CanManageFunds) -> dict[str, str]:
        return {"email": user.email}

    @probe.get("/_probe/cap/move_board")
    async def _probe_move_board(user: CanMoveBoard) -> dict[str, str]:
        return {"email": user.email}

    @probe.get("/_probe/cap/assign_fund")
    async def _probe_assign_fund(user: CanAssignFund) -> dict[str, str]:
        return {"email": user.email}

    @probe.get("/_probe/cap/allocate_funds")
    async def _probe_allocate_funds(user: CanAllocateFunds) -> dict[str, str]:
        return {"email": user.email}

    @probe.get("/_probe/cap/endorse_request")
    async def _probe_endorse_request(user: CanEndorseRequest) -> dict[str, str]:
        return {"email": user.email}

    @probe.get("/_probe/cap/administer_funds")
    async def _probe_administer_funds(user: CanAdministerFunds) -> dict[str, str]:
        return {"email": user.email}

    test_app = FastAPI()
    test_app.include_router(probe, prefix="/api/resource-requests")
    test_app.include_router(module_router, prefix="/api/resource-requests")
    test_app.include_router(access_router, prefix="/api/resource-requests/access")
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
