"""The registration, the guards, and the deny-by-default claim.

Nothing here tests authentication — that is shared surface, already covered. What is tested
is that the app key and the four role keys are the ones the frontend already committed to,
that the guard they hang off admits and refuses the right people, and that **a route added
to this module without a guard of its own is refused anyway**, which is the DoD's third line
and the only one that is a property of the wiring rather than of a call site.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.routing import APIRoute
from sqlalchemy import select

from app.api.shema._deps import APP_KEY
from app.db.models.auth import Role
from app.main import create_app
from app.services.access_request._default_roles import default_role_for
from app.services.authorization import list_roles
from app.services.shema._scope import ROLE_KEYS
from scripts.seed_apps_roles import APP_ROLES_OVERRIDE, SEED_APPS
from tests.baker import grant_app_role, make_app, make_user
from tests.test_shema.conftest import (
    PREFIX,
    ROLE_PROBES,
    SCOPE_PROBE,
    SESSION,
    UNGUARDED_PROBE,
    auth_header,
    grant,
)

#: Paths under ``/api/shema`` that are allowed to carry no authentication.
#:
#: **Empty, and the emptiness is the point today.** BE-12 adds ``GET`` and ``POST``
#: ``/api/shema/intake/{token}`` here — the module's one deliberate hole, by FE-44 §9.0 and
#: ``docs/shema.md`` §6.6, where the token *is* the guard and the guard is a service function
#: so the rule holds for any future caller of it. A route that arrives without a line added
#: here fails ``test_every_shema_route_is_guarded``, which is what makes forgetting a guard
#: a red build rather than an open endpoint.
UNAUTHENTICATED_PATHS: frozenset[str] = frozenset()


def test_the_app_key_is_the_one_three_documents_name() -> None:
    """OBT-390's description, the ecosystem's ``CLAUDE.md`` §3.2 and FE-44's §9 prefix."""
    assert APP_KEY == "shema"


def test_the_app_key_is_named_once_in_the_module() -> None:
    """Where all eight applications in this repository keep theirs.

    The needle is the **quoted** literal and not the bare word, which is the one adaptation
    this module's key forces on the sibling's version of this test: ``shema`` is a substring
    of the route prefix, the package path and the design document's filename, so a bare
    search would fail on every docstring that says where the module lives.
    """
    module = Path(__file__).resolve().parents[2] / "app" / "api" / "shema"
    offenders = [
        path.name
        for path in sorted(module.glob("*.py"))
        if path.name != "_deps.py" and f'"{APP_KEY}"' in path.read_text(encoding="utf-8")
    ]
    assert offenders == [], f"app key duplicated outside _deps.py: {offenders}"


def test_the_seeded_roles_are_the_frontends_session_role_union() -> None:
    """``SessionRole`` in ``src/types/role.ts``, verbatim and camelCase (``docs/shema.md`` §2.3).

    Asserted against ``ROLE_KEYS`` rather than against four literals typed here, because a
    second copy of a four-key vocabulary is the defect the single tuple exists to prevent —
    a test that restates it would go green while the guard and the seed drifted apart.
    """
    assert APP_ROLES_OVERRIDE[APP_KEY] == list(ROLE_KEYS)
    assert ROLE_KEYS == ("globalStrategist", "coordinator", "obtLab", "resourceCircle")


def test_the_seeded_app_carries_the_url_password_reset_is_built_from() -> None:
    """``request_password_reset`` builds ``{app_url}/reset-password?token=…`` from this row.

    Pinned rather than merely well-formed: the failure a wrong value causes is silent, and
    password recovery is the only thing it breaks. ``scripts/seed_apps_roles.py``'s docstring
    records that this value is the convention rather than a hostname read off a deployment,
    because there is no deployment to read.
    """
    entry = next((row for row in SEED_APPS if row[0] == APP_KEY), None)
    assert entry is not None, f"{APP_KEY} missing from SEED_APPS"

    _key, name, app_url = entry
    assert name == "Shemá"
    assert app_url == "https://shema.shemaywam.com"


def test_the_console_origin_is_allowed_by_cors() -> None:
    """The other half of the same change. A seeded ``app_url`` the browser cannot call is
    a link that opens a page whose first request fails."""
    from app.core.config import get_settings

    assert "https://shema.shemaywam.com" in get_settings().cors_origin_list


def test_seed_apps_has_no_duplicate_keys() -> None:
    keys = [row[0] for row in SEED_APPS]
    assert len(keys) == len(set(keys))


def test_an_approved_access_request_grants_a_role_this_app_has() -> None:
    """Without its own entry the dispatch falls back to ``analyst``, which this app does not
    have — approval would raise ``RoleError`` instead of granting. The same regression
    ``translation-helper`` and ``project-health`` each hit once."""
    assert default_role_for(APP_KEY) == "resourceCircle"
    assert default_role_for(APP_KEY) in APP_ROLES_OVERRIDE[APP_KEY]


def test_the_default_role_on_approval_is_not_the_unscoped_one() -> None:
    """The floor an approval hands out must be a **regional** role.

    ``globalStrategist`` is the one key whose reach is every region with no row in
    ``shema_user_regions``, so defaulting to it would make every approved account global —
    the fail-open this module is built to refuse. Asserted separately from the value above
    because it is a different claim: that one says which role, this one says which property
    of it matters.
    """
    from app.services.shema._scope import GLOBAL_ROLE, REGIONAL_ROLES

    assert default_role_for(APP_KEY) != GLOBAL_ROLE
    assert default_role_for(APP_KEY) in REGIONAL_ROLES


def test_every_role_key_has_a_probe() -> None:
    """So the four aliases cannot quietly become three."""
    assert sorted(ROLE_PROBES) == sorted(ROLE_KEYS)


# --- deny by default ---------------------------------------------------------------


def test_every_shema_route_is_guarded() -> None:
    """**The DoD's third line, read off the application the server actually builds.**

    Not a convention and not a review item: every route mounted under ``/api/shema`` must
    carry the app guard, and the only way to be exempt is a line in
    ``UNAUTHENTICATED_PATHS`` above — which is a deliberate edit somebody has to justify,
    rather than a dependency somebody forgot.

    The guard is recognised by ``get_current_user`` appearing in the route's resolved
    dependency chain, which is what both platform guards close over. Asking the chain rather
    than the handler's signature is what makes an inherited router-level dependency count,
    and inheriting it is the whole mechanism.
    """
    from app.core.auth_middleware import get_current_user

    app = create_app()
    unguarded = []
    for route in app.routes:
        if not isinstance(route, APIRoute) or not route.path.startswith(PREFIX):
            continue
        if route.path in UNAUTHENTICATED_PATHS:
            continue
        if not _reaches(route.dependant, get_current_user):
            unguarded.append(f"{sorted(route.methods)} {route.path}")

    assert unguarded == [], f"routes under {PREFIX} with no authentication: {unguarded}"


def _reaches(dependant, target, depth: int = 0) -> bool:
    """Whether ``target`` appears anywhere in ``dependant``'s tree.

    Depth-limited because FastAPI's dependency graph is a tree of arbitrary depth and a
    cycle would hang the suite rather than fail it.
    """
    if depth > 8:
        return False
    for sub in dependant.dependencies:
        if sub.call is target or _reaches(sub, target, depth + 1):
            return True
    return False


def test_every_authenticated_route_reaches_the_application() -> None:
    """The footgun ``app/api/shema/__init__.py``'s last comment names, caught not warned.

    ``include_router`` copies routes at call time, so a sub-router included **after**
    ``router.include_router(authenticated)`` is included into an object the application never
    sees. The route does not raise; it 404s, which is the failure that does not look like
    one. This compares the two sets directly.
    """
    from app.api.shema import authenticated

    app = create_app()
    mounted = {route.path for route in app.routes if isinstance(route, APIRoute)}
    missing = [
        f"{PREFIX}{route.path}"
        for route in authenticated.routes
        if isinstance(route, APIRoute) and f"{PREFIX}{route.path}" not in mounted
    ]
    assert missing == [], (
        "included into `authenticated` after it was mounted, so the application never sees "
        f"it: {missing}"
    )


async def test_an_unguarded_route_is_refused_for_an_account_with_no_grant(
    db_session, client, shema_app
) -> None:
    """**The property, exercised.** The probe declares no dependency of its own; it is
    refused because of where it was included, which is what a later issue inherits."""
    user = await make_user(db_session, email="norole@shema.test")

    res = await client.get(UNGUARDED_PROBE, headers=await auth_header(db_session, user))

    assert res.status_code == 403
    assert APP_KEY in res.json()["detail"]
    assert "contact support" in res.json()["detail"].lower()


async def test_an_unguarded_route_admits_a_granted_account(db_session, client, shema_app) -> None:
    """The other side of the same probe: the guard is a guard, not a wall."""
    user = await make_user(db_session, email="granted@shema.test")
    await grant(db_session, user, shema_app, "coordinator")

    res = await client.get(UNGUARDED_PROBE, headers=await auth_header(db_session, user))

    assert res.status_code == 200


async def test_an_unauthenticated_call_is_refused_before_any_role_is_read(
    client, shema_app
) -> None:
    """No bearer token at all. 401 and not 403 — the caller is nobody, not somebody refused."""
    res = await client.get(UNGUARDED_PROBE)

    assert res.status_code == 401


# --- the guards ---------------------------------------------------------------------


async def test_the_guard_does_not_carry_a_role_over_from_another_app(
    db_session, client, shema_app
) -> None:
    """Access is per application; holding ``coordinator`` somewhere else is not holding it here."""
    other = await make_app(db_session, app_key="some-other-app", name="Other")
    user = await make_user(db_session, email="elsewhere@shema.test")
    await grant_app_role(db_session, user, other, role_key="coordinator")

    res = await client.get(SESSION, headers=await auth_header(db_session, user))

    assert res.status_code == 403


async def test_a_role_alias_refuses_a_member_who_holds_a_different_role(
    db_session, client, shema_app
) -> None:
    """``require_role`` is the tighter of the two gates and this is what it buys.

    The account is a real Shemá member — it passes ``require_app_access`` — and still may
    not reach a route its role does not open. **Not an admin account**, deliberately: an
    admin returns early from both guards and this test would pass with the alias deleted.
    """
    user = await make_user(db_session, email="obtlab@shema.test", is_platform_admin=False)
    await grant(db_session, user, shema_app, "obtLab")
    headers = await auth_header(db_session, user)

    assert (await client.get(ROLE_PROBES["obtLab"], headers=headers)).status_code == 200

    refused = await client.get(ROLE_PROBES["coordinator"], headers=headers)
    assert refused.status_code == 403
    assert "coordinator" in refused.json()["detail"]


async def test_a_platform_admin_passes_without_any_grant(db_session, client, shema_app) -> None:
    """The installation's standing rule, pinned so the tests above cannot drift onto it.

    Refusing an admin inside this module would make one route stricter than the route beside
    it and buy nothing — an admin can grant themselves ``coordinator`` with one call.
    """
    admin = await make_user(db_session, email="admin@shema.test", is_platform_admin=True)
    headers = await auth_header(db_session, admin)

    assert (await client.get(UNGUARDED_PROBE, headers=headers)).status_code == 200
    assert (await client.get(ROLE_PROBES["coordinator"], headers=headers)).status_code == 200


async def test_a_revoked_grant_closes_the_door(db_session, client, shema_app) -> None:
    """``list_roles`` excludes revoked grants, and the guard reads ``list_roles``."""
    from datetime import UTC, datetime

    user = await make_user(db_session, email="revoked@shema.test")
    assignment = await grant(db_session, user, shema_app, "coordinator")
    assignment.revoked_at = datetime.now(UTC)
    await db_session.commit()

    res = await client.get(UNGUARDED_PROBE, headers=await auth_header(db_session, user))

    assert res.status_code == 403


async def test_the_module_never_queries_the_platforms_grant_tables_itself(
    db_session, shema_app
) -> None:
    """``docs/shema.md`` §2.4: a service that reached for ``user_app_roles`` has
    reimplemented ``require_role`` badly. Asked here as a behaviour rather than as a grep,
    because what matters is that the answer comes from the auth spine."""
    user = await make_user(db_session, email="spine@shema.test")
    await grant(db_session, user, shema_app, "resourceCircle")

    assert await list_roles(db_session, user.id, APP_KEY) == [(APP_KEY, "resourceCircle")]


async def test_the_seeded_role_rows_are_what_the_guard_looks_up(db_session, shema_app) -> None:
    """The fixture and the seed script must agree, or every guard test is testing a fixture."""
    stmt = select(Role.role_key).where(Role.app_id == shema_app.id)
    assert sorted((await db_session.execute(stmt)).scalars()) == sorted(ROLE_KEYS)


def test_the_probes_are_removed_after_the_fixture() -> None:
    """The client fixture mutates a module-level router, so it truncates in a ``finally``.

    Asserted so a leak fails here rather than as a mystery extra route in
    ``test_every_shema_route_is_guarded`` two files later.
    """
    from app.api.shema import authenticated

    paths = {route.path for route in authenticated.routes if isinstance(route, APIRoute)}
    assert not any(path.startswith("/_probe") for path in paths)


def test_the_module_router_is_a_plain_router_and_the_guard_is_on_the_inner_one() -> None:
    """The shape BE-12 needs, asserted so it is not simplified away.

    ``router`` carries no dependency of its own: that is what leaves room for the two
    unauthenticated intake routes to be added to it directly, in a line a reviewer sees.
    ``authenticated`` carries the guard, and everything else goes there.
    """
    from app.api.shema import authenticated, router

    assert isinstance(router, APIRouter)
    assert router.dependencies == []
    assert len(authenticated.dependencies) == 1


async def test_the_scope_dependency_is_refused_for_an_account_with_no_grant(
    db_session, client, shema_app
) -> None:
    """The scope dependency chains behind ``CurrentUser``, so an outsider is refused by the
    gate that names the app rather than by an empty scope that silently returns nothing."""
    user = await make_user(db_session, email="noscope@shema.test")

    res = await client.get(SCOPE_PROBE, headers=await auth_header(db_session, user))

    assert res.status_code == 403
