"""Fixtures for the Shemá module's access and scope tests.

The module has one route of its own — ``GET /api/shema/session`` — so the guards are
exercised through it *and* through probe routes defined here. The probes are not a
duplicate of that route: they are what proves the property the session route cannot,
which is that a route added to this module **without a guard of its own** is still refused.
``app/api/shema/__init__.py`` declares ``require_app_access`` once on the ``authenticated``
router, and the unguarded probe hung off that router is the test of it.

**No probe here uses a platform-admin account, and none may.** ``require_app_access`` and
``require_role`` both return early on ``is_platform_admin``, so an admin passes every guard
in this repository; a negative test written per role with an admin account passes for the
wrong reason and would keep passing after the guard was deleted.
"""

from __future__ import annotations

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import select

from app.api.shema._deps import (
    APP_KEY,
    CoordinatorUser,
    CurrentUser,
    GlobalStrategistUser,
    ObtLabUser,
    ResourceCircleUser,
    Scope,
)
from app.db.models.shema import ShemaProject
from app.db.models.shema_enums import ShemaRegionKey
from app.services.shema._scope import ROLE_KEYS
from tests.baker import make_role, make_user, make_user_app_role

PREFIX = "/api/shema"
SESSION = f"{PREFIX}/session"
REGIONS = f"{PREFIX}/regions"
ROLE_CHANGES = f"{REGIONS}/role-changes"
PEOPLE = f"{PREFIX}/prayer/intercessors"

#: The route with **no guard of its own**, hung off the ``authenticated`` router. The whole
#: deny-by-default claim is that this one is refused anyway.
UNGUARDED_PROBE = f"{PREFIX}/_probe/unguarded"
SCOPE_PROBE = f"{PREFIX}/_probe/scope"

#: One probe per role alias, so an alias wired to the wrong key is a real failure rather
#: than an unread line. ``test_access.py`` asserts every key in ``ROLE_KEYS`` has one.
ROLE_PROBES: dict[str, str] = {role: f"{PREFIX}/_probe/role/{role}" for role in ROLE_KEYS}


@pytest.fixture(autouse=True)
def _clear_role_cache():
    """``require_app_access`` memoises roles per ``(user, app_key)`` for 30 seconds.

    Harmless across tests (ids are uuids), fatal inside one: a call made before a grant
    caches the empty list and the grant then appears to do nothing. Clearing around every
    test is what lets one test check both sides of the same account.
    """
    from app.core.auth_cache import _roles_cache

    _roles_cache.clear()
    yield
    _roles_cache.clear()


@pytest.fixture()
async def shema_app(db_session):
    """The app registry row and its four roles — what ``seed_apps_roles.py`` writes.

    ``auto_approve`` is **off**, which is the row production has: Shemá access is granted,
    not registered for. The sibling's is on because GATE-02 D1 answered that whoever
    registers gets in; no such answer exists here, and defaulting to open would be the
    decision this module spends a file arguing against.
    """
    from tests.baker import make_app

    app = await make_app(db_session, app_key=APP_KEY, name="Shemá", auto_approve=False)
    for role_key in ROLE_KEYS:
        await make_role(db_session, app.id, role_key=role_key, label=role_key, is_system=True)
    return app


@pytest.fixture()
async def client(db_session):
    """An ASGI client running the module's real router plus the probes.

    ``authenticated`` is mounted at the prefix the application mounts the module at, so
    ``/api/shema/session`` is exercised through the real dependency chain, and the probes
    are included into that same object — the one every later sub-router will be included
    into — which is what makes the unguarded probe a test of the module's wiring rather
    than of a dependency written here.

    ``router`` itself is deliberately **not** mounted beside it. Everything it carries today
    it carries *through* ``authenticated``, so mounting both would register
    ``/api/shema/session`` twice. The day BE-12 adds the two intake routes to ``router``
    directly, they get their own unauthenticated client rather than sharing this one — and
    ``test_every_shema_route_is_guarded`` reads the real application's route table, which is
    where a route added anywhere in the module is seen whether a fixture mounts it or not.

    The real exception handlers are registered, so ``AuthorizationError`` reaches the wire
    as the 403 a client would receive and ``NotFoundError`` as the 404.

    The dependency aliases are imported at module level on purpose. These handlers are
    defined inside this fixture, so their ``__globals__`` is this module — and with
    ``from __future__ import annotations`` every annotation is a string FastAPI resolves
    against exactly that namespace. Bound locally instead, the name does not resolve,
    FastAPI treats the parameter as a required query parameter, and every guarded call
    answers 422 before the guard ever runs.
    """
    from fastapi import APIRouter, FastAPI

    from app.api.auth import router as auth_router
    from app.api.shema import authenticated
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    probe = APIRouter()

    @probe.get("/_probe/unguarded")
    async def _probe_unguarded() -> dict[str, str]:
        return {"reached": "yes"}

    @probe.get("/_probe/scope")
    async def _probe_scope(scope: Scope) -> dict[str, object]:
        return {"global": scope.global_, "regions": sorted(scope.regions)}

    @probe.get("/_probe/role/globalStrategist")
    async def _probe_global(user: GlobalStrategistUser) -> dict[str, str]:
        return {"email": user.email}

    @probe.get("/_probe/role/coordinator")
    async def _probe_coordinator(user: CoordinatorUser) -> dict[str, str]:
        return {"email": user.email}

    @probe.get("/_probe/role/obtLab")
    async def _probe_obt_lab(user: ObtLabUser) -> dict[str, str]:
        return {"email": user.email}

    @probe.get("/_probe/role/resourceCircle")
    async def _probe_resource_circle(user: ResourceCircleUser) -> dict[str, str]:
        return {"email": user.email}

    @probe.get("/_probe/current")
    async def _probe_current(user: CurrentUser) -> dict[str, str]:
        return {"email": user.email}

    mark = len(authenticated.routes)
    try:
        authenticated.include_router(probe)
        test_app = FastAPI()
        test_app.include_router(authenticated, prefix=PREFIX)
        test_app.include_router(auth_router, prefix="/api/auth")
        register_exception_handlers(test_app)

        async def _get_db():
            yield db_session

        test_app.dependency_overrides[get_db] = _get_db
        transport = ASGITransport(app=test_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            yield c
    finally:
        del authenticated.routes[mark:]


async def auth_header(db_session, user) -> dict[str, str]:
    """A real bearer token for ``user``, decoded by the auth dependency."""
    from app.services.auth.issue_tokens import issue_tokens

    access, _refresh = await issue_tokens(db_session, user)
    return {"Authorization": f"Bearer {access}"}


async def grant(db_session, user, app, role_key: str):
    """Give ``user`` one of the app's already-seeded roles."""
    from app.db.models.auth import Role

    stmt = select(Role).where(Role.app_id == app.id, Role.role_key == role_key)
    role = (await db_session.execute(stmt)).scalar_one()
    return await make_user_app_role(db_session, user.id, app.id, role.id)


async def make_shema_project(
    db_session,
    *,
    project_id: str,
    region_key: ShemaRegionKey,
    language_name: str | None = None,
) -> ShemaProject:
    """One project row, in one region.

    Only the three columns the scope tests read are set. Everything else takes the column
    default, which is what ``docs/shema.md`` §7.4's *two absences* rule wants a fixture to
    do: a fixture that fills every field hides a default that is wrong.
    """
    project = ShemaProject(
        id=project_id,
        language_name=language_name or project_id,
        region_key=region_key,
    )
    db_session.add(project)
    await db_session.commit()
    return project


async def make_scoped_user(
    db_session,
    app,
    *,
    email: str,
    role_key: str,
    regions: list[ShemaRegionKey] | None = None,
):
    """A non-admin account with one Shemá role and an explicit region scope.

    ``is_platform_admin`` is false and is never a parameter: an admin passes every guard,
    so a negative test that used one would pass for the wrong reason.
    """
    from app.services.shema import set_region_scope

    user = await make_user(db_session, email=email, is_platform_admin=False)
    await grant(db_session, user, app, role_key)
    if regions is not None:
        await set_region_scope(db_session, user.id, regions)
    return user


async def make_intercessor(
    client,
    headers: dict[str, str],
    *,
    name: str = "Maria Santos",
    country: str = "BR",
    contact: str = "maria.santos@example.org",
    sensitive: bool = False,
    basis: str = "verbal, at the 2026 regional gathering",
) -> dict:
    """One network contact, through the real endpoint.

    Created over HTTP rather than by inserting a row, because the rule under test in most of
    these files is that a person **cannot** be stored without a recorded basis — a fixture
    that wrote the row directly would be the one caller that proves nothing.
    """
    res = await client.post(
        PEOPLE,
        headers=headers,
        json={
            "name": name,
            "country": country,
            "contact": contact,
            "sensitiveCountry": sensitive,
            "consentBasis": basis,
        },
    )
    assert res.status_code == 201, res.text
    return res.json()
