"""The PME's door — who ``GET /api/shema/session`` admits, and that it admits them to nothing else.

OBT-523, from OBT-522's decision of 25/set: the mesa and the Gestor sign in to the console
holding no Shemá role, their grants living in ``resource-request-form``. So the session sits
on the ``door`` router, which admits an account holding any role of the session's vocabulary
— a Shemá role, the ``admin`` role held in ``shema``, or ``gestor``/``mesa`` held in the form —
and every other route stays behind the Shemá app gate.

The negatives are the point, and each names the role that must not open the door: the form's
``equipe`` (which ``auto_approve`` hands to everybody who registers there), the ``lider`` (who
has no account since 22/set), the form's own ``admin`` row, and an ``admin`` of some other
product. **No account here is an installation admin** except in the test about one: an
installation admin passes every guard, and a refusal proved with one proves nothing.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.db.models.shema_enums import ShemaRegionKey
from app.services import authorization_service
from tests.baker import grant_app_role, make_app, make_user
from tests.test_shema.conftest import (
    DOOR_PROBE,
    PREFIX,
    REGIONS,
    SCOPE_PROBE,
    SESSION,
    UNGUARDED_PROBE,
    auth_header,
    grant,
    make_scoped_user,
)

AFRICA = ShemaRegionKey.AFRICA


async def _form_account(db_session, form_app, email: str, *roles: str):
    user = await make_user(db_session, email=email, is_platform_admin=False)
    for role in roles:
        await grant(db_session, user, form_app, role)
    return user


# --- who passes ------------------------------------------------------------------------


@pytest.mark.parametrize("role", ["mesa", "gestor"])
async def test_an_account_with_only_a_form_seat_passes_the_door(
    db_session, client, shema_app, form_app, role
):
    """The DoD's own case: a mesa or a Gestor, nothing in ``shema``, and the session answers
    — the role it holds, and no region."""
    user = await _form_account(db_session, form_app, f"{role}-only@door.test", role)

    res = await client.get(SESSION, headers=await auth_header(db_session, user))

    assert res.status_code == 200, res.text
    assert res.json()["roles"] == [role]
    assert res.json()["role"] == role
    assert res.json()["regionScope"] == []


async def test_an_account_with_only_the_admin_role_passes_the_door(
    db_session, client, shema_app, form_app
):
    """The ``admin`` role held in ``shema`` — the grant every admin guard below the door reads."""
    user = await make_user(db_session, email="admin-only@door.test")
    await grant(db_session, user, shema_app, "admin")

    res = await client.get(SESSION, headers=await auth_header(db_session, user))

    assert res.status_code == 200, res.text
    assert res.json()["roles"] == ["admin"]
    assert res.json()["regionScope"] == []


async def test_an_installation_admin_passes_the_door_and_is_not_answered_admin(
    db_session, client, shema_app, form_app
):
    """``is_platform_admin`` passes, as it passes every guard — and is not the ``admin`` role:
    holding no grant, the session names none."""
    user = await make_user(db_session, email="installation@door.test", is_platform_admin=True)

    res = await client.get(SESSION, headers=await auth_header(db_session, user))

    assert res.status_code == 200
    assert res.json()["roles"] == []
    assert res.json()["role"] is None


# --- who does not --------------------------------------------------------------------


async def test_an_account_with_no_role_anywhere_is_refused_at_the_door(
    db_session, client, shema_app, form_app
):
    user = await make_user(db_session, email="nobody@door.test")

    res = await client.get(SESSION, headers=await auth_header(db_session, user))

    assert res.status_code == 403
    assert "contact support" in res.json()["detail"].lower()


async def test_the_form_floor_alone_does_not_open_the_door(db_session, client, shema_app, form_app):
    """Everybody who registers in the form is ``equipe`` — counting it would open the console to
    anyone with an account. ``equipe`` becomes a project membership in OBT-524, not a door."""
    user = await _form_account(db_session, form_app, "floor@door.test", "equipe")

    res = await client.get(SESSION, headers=await auth_header(db_session, user))

    assert res.status_code == 403


async def test_the_leader_alone_does_not_open_the_door(db_session, client, shema_app, form_app):
    """The Líder de Base endorses by link and has no account since 22/set."""
    user = await _form_account(db_session, form_app, "leader@door.test", "lider")

    res = await client.get(SESSION, headers=await auth_header(db_session, user))

    assert res.status_code == 403


async def test_an_admin_granted_only_in_the_form_does_not_open_the_door(
    db_session, client, shema_app, form_app
):
    """The form's ``admin`` row is the same role in the other app, and every admin guard of the
    PME reads the ``shema`` one: a session saying *admin* here would name a power every admin
    route then refuses. OBT-543 grants the two together."""
    user = await _form_account(db_session, form_app, "formadmin@door.test", "admin")

    res = await client.get(SESSION, headers=await auth_header(db_session, user))

    assert res.status_code == 403


async def test_an_admin_of_another_application_does_not_open_the_door(
    db_session, client, shema_app, form_app
):
    """Six products seed an ``admin``; the key is counted only from the app it belongs to."""
    other = await make_app(db_session, app_key="tripod-studio", name="Tripod Studio")
    user = await make_user(db_session, email="elsewhere-admin@door.test")
    await grant_app_role(db_session, user, other, role_key="admin")

    res = await client.get(SESSION, headers=await auth_header(db_session, user))

    assert res.status_code == 403


async def test_a_revoked_mesa_grant_closes_the_door(db_session, client, shema_app, form_app):
    user = await make_user(db_session, email="revoked-mesa@door.test")
    assignment = await grant(db_session, user, form_app, "mesa")
    assignment.revoked_at = datetime.now(UTC)
    await db_session.commit()

    res = await client.get(SESSION, headers=await auth_header(db_session, user))

    assert res.status_code == 403


async def test_an_unauthenticated_call_to_the_door_is_a_401(client, shema_app):
    assert (await client.get(SESSION)).status_code == 401


# --- the door opens one route --------------------------------------------------------


async def test_the_door_opens_the_session_and_nothing_else(db_session, client, shema_app, form_app):
    """A mesa gets its session and is refused everywhere else — the app gate still stands in
    front of every route under ``authenticated``, guarded or not."""
    user = await _form_account(db_session, form_app, "mesa-door@door.test", "mesa")
    headers = await auth_header(db_session, user)

    assert (await client.get(SESSION, headers=headers)).status_code == 200
    for path in (UNGUARDED_PROBE, SCOPE_PROBE, f"{PREFIX}/projects", REGIONS):
        assert (await client.get(path, headers=headers)).status_code == 403, path


async def test_a_route_added_behind_the_door_without_a_guard_is_still_guarded(
    db_session, client, shema_app, form_app
):
    """The door is a router-level dependency, so a route hung off it later inherits it: refused
    to nobody, admitted to a Gestor, 401 without a token."""
    nobody = await make_user(db_session, email="nobody-probe@door.test")
    gestor = await _form_account(db_session, form_app, "gestor-probe@door.test", "gestor")

    assert (await client.get(DOOR_PROBE)).status_code == 401
    refused = await client.get(DOOR_PROBE, headers=await auth_header(db_session, nobody))
    assert refused.status_code == 403
    admitted = await client.get(DOOR_PROBE, headers=await auth_header(db_session, gestor))
    assert admitted.status_code == 200


async def test_the_session_reads_the_grants_once_per_request(
    db_session, client, shema_app, form_app, monkeypatch
):
    """The door and the body are one read: the door's roles are the ones the handler answers,
    solved once by FastAPI — which is also why they cannot disagree."""
    user = await _form_account(db_session, form_app, "once@door.test", "mesa")
    headers = await auth_header(db_session, user)
    real = authorization_service.list_roles
    calls: list[str | None] = []

    async def counting(db, user_id, app_key=None):
        calls.append(app_key)
        return await real(db, user_id, app_key)

    monkeypatch.setattr(authorization_service, "list_roles", counting)

    assert (await client.get(SESSION, headers=headers)).status_code == 200
    assert calls == [None]


# --- the region stays the regional roles' ---------------------------------------------


@pytest.mark.parametrize("regional", ["coordinator", "obtLab", "resourceCircle"])
@pytest.mark.parametrize("extra", ["admin", "gestor", "mesa"])
async def test_the_session_scope_of_a_regional_role_is_unchanged_beside_a_new_role(
    db_session, client, shema_app, form_app, regional, extra
):
    user = await make_scoped_user(
        db_session,
        shema_app,
        email=f"{regional.lower()}-{extra}@door.test",
        role_key=regional,
        regions=[AFRICA],
    )
    await grant(db_session, user, shema_app if extra == "admin" else form_app, extra)

    res = await client.get(SESSION, headers=await auth_header(db_session, user))

    assert res.json()["regionScope"] == ["africa"]
    assert res.json()["role"] == regional


@pytest.mark.parametrize("role", ["admin", "gestor", "mesa"])
async def test_admin_gestor_and_mesa_reach_no_region_even_with_a_region_row(
    db_session, client, shema_app, form_app, role
):
    """A row left in ``shema_user_regions`` — a revoked coordinator's, an org-chart seat's — is
    the reach of a regional role, and these three are not one."""
    from app.services.shema import set_region_scope

    user = await make_user(db_session, email=f"{role}-row@door.test")
    await grant(db_session, user, shema_app if role == "admin" else form_app, role)
    await set_region_scope(db_session, user.id, [AFRICA])

    res = await client.get(SESSION, headers=await auth_header(db_session, user))

    assert res.status_code == 200
    assert res.json()["regionScope"] == []
