"""Who reaches the Admin's surface, and the raw tool it closes — OBT-543's first and fifth lines.

Only the ``admin`` role of the Shemá app reaches ``/api/shema/access``. A Gestor or a mesa —
whose grants live in the form — is refused by the app gate of the ``authenticated`` router;
a coordinator, an OBT Lab, a Resource Circle or a global strategist by the Admin guard itself.
And the raw ``/api/roles/assign`` and ``/revoke`` no longer take the two apps' roles from an
Admin, because every rule the surface applies would be one request away from being skipped.

**No refusal here is proved with an installation admin**, who passes every guard; the tests
about one say so in their names.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import get_args

import pytest
from fastapi.routing import APIRoute
from sqlalchemy import select

from app.api.shema._deps import APP_KEY, FORM_APP_KEY, AdminUser
from app.db.models.auth import Role, UserAppRole
from app.main import create_app
from tests.baker import make_app, make_role, make_user
from tests.shema_admin_harness import (
    CHANGES,
    GRANTS,
    INVITES,
    PEOPLE,
    REVOKE,
    WITHDRAW,
    make_account,
    make_admin,
    surface_client,
)
from tests.shema_harness import reaches
from tests.test_shema.conftest import auth_header, grant

#: The surface, pinned: a route added under ``/access`` is an edit to this set, and every one
#: of them must carry the Admin guard.
ADMIN_ROUTES: frozenset[tuple[str, str]] = frozenset(
    {
        ("GET", PEOPLE),
        ("POST", GRANTS),
        ("POST", REVOKE),
        ("POST", INVITES),
        ("POST", WITHDRAW),
        ("GET", INVITES),
        ("GET", CHANGES),
    }
)


async def _calls(client, headers, target_id: str, target_email: str):
    """One valid request per route — a refusal must be the guard's, never the payload's."""
    return {
        ("GET", PEOPLE): await client.get(PEOPLE, params={"email": target_email}, headers=headers),
        ("POST", GRANTS): await client.post(
            GRANTS,
            json={"userId": target_id, "appKey": APP_KEY, "roleKey": "globalStrategist"},
            headers=headers,
        ),
        ("POST", REVOKE): await client.post(
            REVOKE,
            json={"userId": target_id, "appKey": APP_KEY, "roleKey": "globalStrategist"},
            headers=headers,
        ),
        ("POST", INVITES): await client.post(
            INVITES,
            json={"email": "someone@shema.example", "appKey": FORM_APP_KEY, "roleKey": "mesa"},
            headers=headers,
        ),
        ("POST", WITHDRAW): await client.post(
            WITHDRAW, json={"inviteId": "no-such-invite"}, headers=headers
        ),
        ("GET", INVITES): await client.get(INVITES, headers=headers),
        ("GET", CHANGES): await client.get(CHANGES, headers=headers),
    }


# --- only the Admin ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("role", "app_name"),
    [
        ("gestor", "form"),
        ("mesa", "form"),
        ("coordinator", "shema"),
        ("globalStrategist", "shema"),
        ("obtLab", "shema"),
        ("resourceCircle", "shema"),
    ],
)
async def test_every_admin_route_refuses_a_persona_that_is_not_the_admin(
    db_session, shema_app, form_app, role, app_name
) -> None:
    """The DoD's own three — ``gestor``, ``coordinator``, ``globalStrategist`` — and the rest.

    The form's seats stop at the app gate (they hold nothing in ``shema``); the Shemá
    personas pass it and stop at the Admin guard. Nothing is written either way.
    """
    app = form_app if app_name == "form" else shema_app
    persona = await make_account(db_session, f"{role.lower()}@shema.example", (app, role))
    target = await make_account(db_session, "target@shema.example")
    headers = await auth_header(db_session, persona)

    async with surface_client(db_session) as client:
        answers = await _calls(client, headers, target.id, target.email)

    for route, res in answers.items():
        assert res.status_code == 403, (route, res.text)
        expected = "application" if app_name == "form" else "Role 'admin' is required"
        assert expected in res.json()["detail"], route
    held = select(UserAppRole.id).where(UserAppRole.user_id == target.id)
    assert (await db_session.execute(held)).all() == []


async def test_the_admin_reaches_every_admin_route(db_session, shema_app, form_app) -> None:
    """The other side of the same seven calls: the guard is a guard, not a wall."""
    _admin, headers = await make_admin(db_session, shema_app, form_app)
    target = await make_account(db_session, "target@shema.example")

    async with surface_client(db_session) as client:
        answers = await _calls(client, headers, target.id, target.email)

    reached = {route: res.status_code for route, res in answers.items()}
    assert reached == {
        ("GET", PEOPLE): 200,
        ("POST", GRANTS): 200,
        ("POST", REVOKE): 200,
        ("POST", INVITES): 201,
        ("POST", WITHDRAW): 404,
        ("GET", INVITES): 200,
        ("GET", CHANGES): 200,
    }


async def test_an_installation_admin_reaches_the_surface(db_session, shema_app, form_app) -> None:
    """The installation's standing rule: an installation admin passes every guard here too."""
    installation = await make_user(
        db_session, email="installation@shema.example", is_platform_admin=True
    )
    target = await make_account(db_session, "target@shema.example")
    headers = await auth_header(db_session, installation)

    async with surface_client(db_session) as client:
        res = await client.post(
            GRANTS,
            json={"userId": target.id, "appKey": APP_KEY, "roleKey": "admin"},
            headers=headers,
        )

    assert res.status_code == 200, res.text
    assert [entry["roles"] for entry in res.json()["apps"]] == [["admin"], ["admin"]]


async def test_an_admin_held_only_in_the_form_is_refused(db_session, shema_app, form_app) -> None:
    """The form's ``admin`` row is not the PME's Admin: every guard below the door reads
    ``shema``'s, and this account stops at the app gate."""
    form_only = await make_account(db_session, "form-admin@shema.example", (form_app, "admin"))
    target = await make_account(db_session, "target@shema.example")

    async with surface_client(db_session) as client:
        res = await client.get(
            PEOPLE,
            params={"email": target.email},
            headers=await auth_header(db_session, form_only),
        )

    assert res.status_code == 403


async def test_an_admin_missing_the_form_row_is_refused_before_anything_is_written(
    db_session, shema_app, form_app
) -> None:
    """An Admin granted in ``shema`` alone — by hand, or before this surface existed — passes
    the route and may not write the form's roles: the platform's own predicate is read fresh,
    answered as a 403, and says what is missing."""
    admin = await make_account(db_session, "half-admin@shema.example", (shema_app, "admin"))
    target = await make_account(db_session, "target@shema.example")

    async with surface_client(db_session) as client:
        res = await client.post(
            GRANTS,
            json={"userId": target.id, "appKey": FORM_APP_KEY, "roleKey": "mesa"},
            headers=await auth_header(db_session, admin),
        )

    assert res.status_code == 403
    assert FORM_APP_KEY in res.json()["detail"]
    held = select(UserAppRole.id).where(UserAppRole.user_id == target.id)
    assert (await db_session.execute(held)).all() == []


async def test_a_stale_admin_is_refused_before_anything_is_written(
    db_session, shema_app, form_app
) -> None:
    """``AdminUser`` answers from a cache up to thirty seconds old; a write reads the grant
    as it stands. An Admin revoked a moment ago — here by a write the cache never heard of —
    still gets past the route and is refused by the write."""
    admin, headers = await make_admin(db_session, shema_app, form_app)
    target = await make_account(db_session, "target@shema.example")

    async with surface_client(db_session) as client:
        warm = await client.get(PEOPLE, params={"email": target.email}, headers=headers)
        assert warm.status_code == 200
        rows = await db_session.execute(select(UserAppRole).where(UserAppRole.user_id == admin.id))
        for row in rows.scalars():
            row.revoked_at = datetime.now(UTC)
        await db_session.commit()

        res = await client.post(
            GRANTS,
            json={"userId": target.id, "appKey": APP_KEY, "roleKey": "globalStrategist"},
            headers=headers,
        )

    assert res.status_code == 403
    held = select(UserAppRole.id).where(UserAppRole.user_id == target.id)
    assert (await db_session.execute(held)).all() == []


def test_the_seven_routes_are_pinned_and_each_carries_the_admin_guard() -> None:
    """Read off the application the server builds. Pinned, so this cannot pass on an empty
    set, and so an eighth route under ``/access`` is an edit somebody has to justify."""
    admin_check = get_args(AdminUser)[1].dependency
    app = create_app()
    mounted = {
        (method, route.path): route
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/api/shema/access")
        for method in route.methods or ()
    }

    assert set(mounted) == ADMIN_ROUTES
    unguarded = [key for key, route in mounted.items() if not reaches(route.dependant, admin_check)]
    assert unguarded == []


async def test_an_unauthenticated_call_is_a_401(db_session, shema_app) -> None:
    """No bearer token: the caller is nobody, not somebody refused."""
    async with surface_client(db_session) as client:
        answers = await _calls(client, {}, "anyone", "anyone@shema.example")

    assert {res.status_code for res in answers.values()} == {401}


# --- the raw tool, closed for the two apps ----------------------------------------------


async def test_the_raw_role_routes_refuse_the_two_apps_to_an_admin(
    db_session, shema_app, form_app
) -> None:
    """The three ways around the surface's rules, each a single request before OBT-543:
    granting yourself the global role, seating a Gestor at the mesa, and revoking with no
    trace of who did it. All three are 403 now, and nothing is written."""
    admin, headers = await make_admin(db_session, shema_app, form_app)
    gestor = await make_account(db_session, "gestor@shema.example", (form_app, "gestor"))

    async with surface_client(db_session) as client:
        to_self = await client.post(
            "/api/roles/assign",
            json={"target_user_id": admin.id, "app_key": APP_KEY, "role_key": "globalStrategist"},
            headers=headers,
        )
        seat = await client.post(
            "/api/roles/assign",
            json={"target_user_id": gestor.id, "app_key": FORM_APP_KEY, "role_key": "mesa"},
            headers=headers,
        )
        revoke = await client.post(
            "/api/roles/revoke",
            json={"target_user_id": gestor.id, "app_key": FORM_APP_KEY, "role_key": "gestor"},
            headers=headers,
        )

    for res in (to_self, seat, revoke):
        assert res.status_code == 403, res.text
        assert "/api/shema/access" in res.json()["detail"]
    live = (
        select(Role.role_key)
        .join(UserAppRole, UserAppRole.role_id == Role.id)
        .where(UserAppRole.revoked_at.is_(None))
    )
    held = sorted((await db_session.execute(live)).scalars())
    assert held == ["admin", "admin", "gestor"]


async def test_an_installation_admin_still_uses_the_raw_routes(
    db_session, shema_app, form_app
) -> None:
    installation = await make_user(
        db_session, email="installation@shema.example", is_platform_admin=True
    )
    target = await make_account(db_session, "target@shema.example")

    async with surface_client(db_session) as client:
        res = await client.post(
            "/api/roles/assign",
            json={"target_user_id": target.id, "app_key": APP_KEY, "role_key": "coordinator"},
            headers=await auth_header(db_session, installation),
        )

    assert res.status_code == 200, res.text


async def test_another_apps_admin_still_uses_the_raw_routes(db_session) -> None:
    """The closure is two app keys wide and no wider."""
    other = await make_app(db_session, app_key="oral-collector", name="Oral Collector")
    await make_role(db_session, other.id, role_key="admin", label="Admin")
    await make_role(db_session, other.id, role_key="member", label="Member")
    admin = await make_user(db_session, email="oc-admin@shema.example")
    await grant(db_session, admin, other, "admin")
    target = await make_user(db_session, email="oc-member@shema.example")

    async with surface_client(db_session) as client:
        res = await client.post(
            "/api/roles/assign",
            json={"target_user_id": target.id, "app_key": "oral-collector", "role_key": "member"},
            headers=await auth_header(db_session, admin),
        )

    assert res.status_code == 200, res.text


def test_the_raw_route_constant_is_the_modules_two_keys() -> None:
    """Written a second time in ``app/api/roles.py``; this is what keeps the two from drifting."""
    from app.api.roles import PME_APP_KEYS

    assert frozenset({APP_KEY, FORM_APP_KEY}) == PME_APP_KEYS


# --- /api/roles/check ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("role", "app_name"),
    [("coordinator", "shema"), ("globalStrategist", "shema"), ("gestor", "form")],
)
async def test_roles_check_refuses_a_persona_probing_another_account(
    db_session, shema_app, form_app, role, app_name
) -> None:
    """The DoD's fifth line. ``dev`` requires the app's ``admin`` — or an installation admin —
    to ask about somebody else since OBT-506; these are the personas of this surface, held to
    it. 400, because the refusal is the platform's shared predicate and eight apps read it."""
    app = form_app if app_name == "form" else shema_app
    prober = await make_account(db_session, f"{role.lower()}@shema.example", (app, role))
    admin, _headers = await make_admin(db_session, shema_app, form_app)

    async with surface_client(db_session) as client:
        res = await client.get(
            "/api/roles/check",
            params={"user_id": admin.id, "app_key": APP_KEY, "role_key": "admin"},
            headers=await auth_header(db_session, prober),
        )

    assert res.status_code == 400
    assert "cannot manage roles" in res.json()["detail"]


async def test_roles_check_answers_the_admin_about_another_account(
    db_session, shema_app, form_app
) -> None:
    _admin, headers = await make_admin(db_session, shema_app, form_app)
    target = await make_account(db_session, "coord@shema.example", (shema_app, "coordinator"))

    async with surface_client(db_session) as client:
        res = await client.get(
            "/api/roles/check",
            params={"user_id": target.id, "app_key": APP_KEY, "role_key": "coordinator"},
            headers=headers,
        )

    assert res.status_code == 200
    assert res.json() == {"allowed": True}
