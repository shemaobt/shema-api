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

from app.api.shema._deps import APP_KEY, FORM_APP_KEY
from app.db.models.auth import Role
from app.main import create_app
from app.services.access_request._default_roles import default_role_for
from app.services.authorization import list_roles
from app.services.shema._scope import ROLE_KEYS, ROLE_PRECEDENCE, SHEMA_APP_ROLES
from scripts.seed_apps_roles import APP_ROLES_OVERRIDE, SEED_APPS, seeded_roles
from tests.baker import grant_app_role, make_app, make_user
from tests.shema_harness import UNAUTHENTICATED_PATHS, reaches
from tests.test_shema.conftest import (
    PREFIX,
    ROLE_PROBES,
    SCOPE_PROBE,
    SESSION,
    UNGUARDED_PROBE,
    auth_header,
    grant,
)

#: Routes behind the PME's door rather than the Shemá app gate (OBT-523): reachable by an
#: account holding ``gestor`` or ``mesa`` in the form, or only a live project membership, and
#: nothing in ``shema``. The session, OBT-524's two reads a member has, and OBT-541's panel and
#: read mark — the form's notices are addressed to those accounts; a sixth is a line somebody
#: adds here on purpose.
#:
#: **Keyed by method and path**, since OBT-524 put a ``GET`` behind the door and the Admin's
#: ``POST`` behind the app gate on one path, ``/projects/{project_id}/members``. Keyed by path
#: alone, a ``PUT`` hung off the door on that path later — with no ``AdminUser`` — would pass
#: here as the ``GET`` already listed. BE-06 made ``COORDINATION_ROUTES`` pairs for the same
#: reason.
DOOR_ROUTES: frozenset[tuple[str, str]] = frozenset(
    {
        ("GET", f"{PREFIX}/session"),
        ("GET", f"{PREFIX}/projects/{{project_id}}/members"),
        ("GET", f"{PREFIX}/me/projects"),
        ("GET", f"{PREFIX}/notifications"),
        ("POST", f"{PREFIX}/notifications/read"),
    }
)


def _pairs(routes, prefix: str = "") -> set[tuple[str, str]]:
    """Every ``(method, path)`` a route list serves; ``HEAD`` and ``OPTIONS`` are not counted."""
    return {
        (method, f"{prefix}{route.path}")
        for route in routes
        if isinstance(route, APIRoute)
        for method in sorted(set(route.methods or ()) - {"HEAD", "OPTIONS"})
    }


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


def test_the_seeded_roles_are_the_three_shema_roles_and_the_admin() -> None:
    """The four personas FE-44 drew the console for, verbatim and camelCase (``docs/shema.md``
    §2.3), plus OBT-522's ``admin`` — which is seeded as one entry for two apps rather than as
    a fifth key in the override.

    Asserted against ``ROLE_KEYS`` rather than against literals typed here, because a second
    copy of the vocabulary is the defect the single tuple exists to prevent (the fourth key,
    the Global Strategist's, left with OBT-572) —
    a test that restates it would go green while the guard and the seed drifted apart.
    """
    assert APP_ROLES_OVERRIDE[APP_KEY] == list(ROLE_KEYS)
    assert ROLE_KEYS == ("coordinator", "obtLab", "resourceCircle")
    assert [key for key, _label in seeded_roles(APP_KEY)] == list(SHEMA_APP_ROLES)


def test_the_session_vocabulary_is_the_frontends_in_precedence_order() -> None:
    """``SESSION_ROLES`` in the console's ``src/constants/roles.ts``, key for key and in the
    same order — the console refuses a session carrying any key outside it, so a key added
    here and not there locks people out, and the order is the ``role`` the console renders."""
    assert ROLE_PRECEDENCE == (
        "coordinator",
        "obtLab",
        "resourceCircle",
        "admin",
        "gestor",
        "mesa",
        "equipe",
    )


def test_the_forms_app_key_here_is_the_forms_own() -> None:
    """Written a second time in ``_deps.py``, as ``get_rr_app_id.py`` writes it; this is what
    keeps the two from drifting apart in silence."""
    from app.api.resource_requests._deps import APP_KEY as FORMS_OWN

    assert FORM_APP_KEY == FORMS_OWN


def test_the_form_seats_the_session_names_are_the_forms_own() -> None:
    """``gestor``, ``mesa`` and ``equipe`` are the form's ids verbatim; a rename over there must
    fail here rather than close the door on the mesa."""
    from app.services.resource_request.capabilities import ROLES
    from app.services.shema._scope import EQUIPE_ROLE, FORM_DOOR_ROLES

    assert set(FORM_DOOR_ROLES) | {EQUIPE_ROLE} <= set(ROLES)


def test_the_seeded_app_carries_the_url_password_reset_is_built_from() -> None:
    """``request_password_reset`` builds ``{app_url}/reset-password?token=…`` from this row.

    Pinned rather than merely well-formed: the failure a wrong value causes is silent, and it
    breaks every letter built from this row — the password reset, the invite
    (``send_invite``, ``/convite?token=…``), the intercessor's leave link (``/leave/<token>``)
    and the intake link — none of which says so until somebody clicks. BE-03 pinned a
    conventional hostname here and it never got a DNS record; since OBT-567 the value is the
    Cloud Run address the PME answers on, and ``tests/test_shema/test_pme_app_url.py`` holds
    the seed and the data migration that corrects installed rows to the same value.
    """
    entry = next((row for row in SEED_APPS if row[0] == APP_KEY), None)
    assert entry is not None, f"{APP_KEY} missing from SEED_APPS"

    _key, name, app_url = entry
    assert name == "Shemá"
    assert app_url == "https://project-management-ecosystem-f7ssqjozfq-uc.a.run.app"


def test_the_console_origin_is_allowed_by_cors() -> None:
    """The other half of BE-03's change. A seeded ``app_url`` the browser cannot call is a
    link that opens a page whose first request fails.

    Still the retired hostname, on purpose: ``cors_origins`` is ``app/core/config.py``, the
    platform core, and OBT-567 changed the seed and the installed row without touching it.
    The deployed PME never needed an entry here: its own nginx proxies ``/api`` to
    ``$BACKEND_URL`` (``project-management-ecosystem/nginx.conf``), so the browser calls the
    API on the PME's origin and CORS is never consulted — the deploy workflows set
    ``CORS_ORIGINS`` without it and it works. Retiring this entry is the core's own change.
    """
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


def test_the_default_role_on_approval_is_a_regional_one() -> None:
    """The floor an approval hands out must be a **regional** role.

    An unscoped key — one whose reach is every region with no row in ``shema_user_regions`` —
    would make every approved account global, the fail-open this module is built to refuse.
    OBT-572 retired the one such key, so every Shemá role is regional now and the floor is
    one of them. Asserted separately from the value above because it is a different claim:
    that one says which role, this one says which property of it matters.
    """
    from app.services.shema._scope import REGIONAL_ROLES, ROLE_KEYS

    assert set(ROLE_KEYS) <= set(REGIONAL_ROLES)
    assert default_role_for(APP_KEY) in REGIONAL_ROLES


def test_every_role_key_has_a_probe() -> None:
    """So the five aliases — the four and the Admin — cannot quietly become four."""
    assert sorted(ROLE_PROBES) == sorted(SHEMA_APP_ROLES)


# --- deny by default ---------------------------------------------------------------


def test_every_shema_route_is_guarded() -> None:
    """**The DoD's third line, read off the application the server actually builds.**

    Not a convention and not a review item: every route mounted under ``/api/shema`` must
    carry the app guard, and the only way to be exempt is a line in
    ``UNAUTHENTICATED_PATHS`` (``tests/shema_harness.py``) — which is a deliberate edit
    somebody has to justify, rather than a dependency somebody forgot.

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
        if not reaches(route.dependant, get_current_user):
            unguarded.append(f"{sorted(route.methods)} {route.path}")

    assert unguarded == [], f"routes under {PREFIX} with no authentication: {unguarded}"


def test_only_the_listed_paths_sit_behind_the_door() -> None:
    """The door admits accounts the Shemá app gate would refuse, so what sits behind it is a
    list somebody edits on purpose — read off the application the server builds."""
    from app.api.shema import door

    behind = _pairs(door.routes, PREFIX)
    mounted = _pairs(create_app().routes)

    assert behind == DOOR_ROUTES
    assert behind <= mounted, "a door route was included after the door was mounted"


def test_every_authenticated_route_reaches_the_application() -> None:
    """The footgun ``app/api/shema/__init__.py``'s last comment names, caught not warned.

    ``include_router`` copies routes at call time, so a sub-router included **after**
    ``router.include_router(authenticated)`` is included into an object the application never
    sees. The route does not raise; it 404s, which is the failure that does not look like
    one. This compares the two sets directly, by method and path: since OBT-524 a path can be
    served by the door for one method and by ``authenticated`` for another, and a path already
    mounted through the door would hide a ``POST`` that never arrived.
    """
    from app.api.shema import authenticated

    mounted = _pairs(create_app().routes)
    missing = sorted(_pairs(authenticated.routes, PREFIX) - mounted)
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


async def test_the_admin_alias_admits_the_shema_admin_and_refuses_every_other_persona(
    db_session, client, shema_app, form_app
) -> None:
    """``AdminUser`` reads the ``admin`` role in ``shema``. Every other Shemá persona is refused
    by it, and the form's ``admin`` row does not get past the app gate at all. **Not** an
    installation admin, which would pass for the wrong reason."""
    admin = await make_user(db_session, email="the-admin@shema.test")
    await grant(db_session, admin, shema_app, "admin")
    assert (
        await client.get(ROLE_PROBES["admin"], headers=await auth_header(db_session, admin))
    ).status_code == 200

    for role in ROLE_KEYS:
        other = await make_user(db_session, email=f"not-admin-{role.lower()}@shema.test")
        await grant(db_session, other, shema_app, role)
        res = await client.get(ROLE_PROBES["admin"], headers=await auth_header(db_session, other))
        assert res.status_code == 403, role

    form_admin = await make_user(db_session, email="form-admin@shema.test")
    await grant(db_session, form_admin, form_app, "admin")
    res = await client.get(ROLE_PROBES["admin"], headers=await auth_header(db_session, form_admin))
    assert res.status_code == 403


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
    assert sorted((await db_session.execute(stmt)).scalars()) == sorted(SHEMA_APP_ROLES)


def test_the_probes_are_removed_after_the_fixture() -> None:
    """The test app fixture mutates a module-level router, so it truncates in a ``finally``.

    Asserted so a leak fails here rather than as a mystery extra route in
    ``test_every_shema_route_is_guarded`` two files later.
    """
    from app.api.shema import authenticated, door

    for mutated in (authenticated, door):
        paths = {route.path for route in mutated.routes if isinstance(route, APIRoute)}
        assert not any(path.startswith("/_probe") for path in paths)


def test_the_module_router_carries_no_guard_and_the_guard_is_on_the_inner_one() -> None:
    """The shape BE-12 needs, asserted so it is not simplified away.

    ``router`` carries no guard of its own: that is what leaves room for the two
    unauthenticated intake routes to be added to it directly, in a line a reviewer sees.
    ``authenticated`` carries the guard, and everything else goes there. Its one dependency is
    OBT-555's cache rule, which admits everybody and refuses nobody —
    ``tests/test_shema/test_cache_control.py`` is where it is held to what it writes.
    """
    from app.api.shema import authenticated, door, router
    from app.api.shema._deps import NO_STORE

    assert isinstance(router, APIRouter)
    assert router.dependencies == [NO_STORE]
    assert len(authenticated.dependencies) == 1
    assert len(door.dependencies) == 1


async def test_the_scope_dependency_is_refused_for_an_account_with_no_grant(
    db_session, client, shema_app
) -> None:
    """The scope dependency chains behind ``CurrentUser``, so an outsider is refused by the
    gate that names the app rather than by an empty scope that silently returns nothing."""
    user = await make_user(db_session, email="noscope@shema.test")

    res = await client.get(SCOPE_PROBE, headers=await auth_header(db_session, user))

    assert res.status_code == 403
