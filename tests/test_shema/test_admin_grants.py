"""What the Admin's grants write — roles, regions, the rules, and the history of all of it.

OBT-543's second, third, sixth and seventh lines, through the real routes. A regional role is
granted with its regions or not at all, and the regions land in ``shema_user_regions``; mesa
and Gestor never share an account and nobody grants or revokes their own role; ``admin`` is
written in both apps; and every grant and revocation — of a role, and of a region — is in
``changes`` with its author and its date.

Every account here is an ordinary one: the Admin holds ``admin`` in both apps and is not an
installation admin (``tests/shema_admin_harness.py``).
"""

from __future__ import annotations

import pytest
from sqlalchemy import select, update
from sqlalchemy.exc import DBAPIError

from app.api.shema._deps import APP_KEY, FORM_APP_KEY
from app.db.models.auth import App, Role, UserAppRole
from app.db.models.shema_enums import ShemaRegionKey
from app.db.models.shema_grant import ShemaScopeChange
from app.db.models.shema_region import ShemaUserRegion
from app.services.shema import GrantApps, list_grant_changes, set_region_scope
from app.services.shema._grant_rules import grantable_roles
from app.services.shema._scope import (
    ADMIN_ROLE,
    FORM_DOOR_ROLES,
    REGIONAL_ROLES,
    SHEMA_APP_ROLES,
)
from app.services.user.delete_user import delete_user
from tests.shema_admin_harness import (
    CHANGES,
    GRANTS,
    PEOPLE,
    REVOKE,
    make_account,
    make_admin,
    surface_client,
)
from tests.test_shema.conftest import SESSION, auth_header

APPS = GrantApps(shema=APP_KEY, form=FORM_APP_KEY)


def _grant(user_id: str, role: str, app: str = APP_KEY, regions: list[str] | None = None):
    body: dict[str, object] = {"userId": user_id, "appKey": app, "roleKey": role}
    if regions is not None:
        body["regionKeys"] = regions
    return body


async def _live_roles(db_session, user_id: str) -> list[tuple[str, str]]:
    stmt = (
        select(App.app_key, Role.role_key)
        .join(Role, Role.app_id == App.id)
        .join(UserAppRole, UserAppRole.role_id == Role.id)
        .where(UserAppRole.user_id == user_id, UserAppRole.revoked_at.is_(None))
    )
    return sorted((await db_session.execute(stmt)).tuples().all())


async def _regions(db_session, user_id: str) -> list[tuple[str, str | None]]:
    stmt = select(ShemaUserRegion.region_key, ShemaUserRegion.granted_by).where(
        ShemaUserRegion.user_id == user_id
    )
    return sorted((key.value, by) for key, by in (await db_session.execute(stmt)).all())


# --- the account ----------------------------------------------------------------------


async def test_an_account_is_found_by_exact_email_with_roles_per_app_and_regions(
    db_session, shema_app, form_app
) -> None:
    _admin, headers = await make_admin(db_session, shema_app, form_app)
    person = await make_account(
        db_session,
        "person@shema.example",
        (shema_app, "coordinator"),
        (form_app, "gestor"),
        (form_app, "equipe"),
    )
    await set_region_scope(db_session, person.id, [ShemaRegionKey.AFRICA])

    async with surface_client(db_session) as client:
        res = await client.get(PEOPLE, params={"email": " Person@Shema.example "}, headers=headers)

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["userId"] == person.id
    assert body["apps"] == [
        {"appKey": APP_KEY, "roles": ["coordinator"]},
        {"appKey": FORM_APP_KEY, "roles": ["gestor"]},
    ]
    assert [row["regionKey"] for row in body["regions"]] == ["africa"]
    assert body["regionScope"] == ["africa"]


async def test_an_unknown_email_is_a_404(db_session, shema_app, form_app) -> None:
    _admin, headers = await make_admin(db_session, shema_app, form_app)

    async with surface_client(db_session) as client:
        res = await client.get(PEOPLE, params={"email": "nobody@shema.example"}, headers=headers)

    assert res.status_code == 404
    assert res.json()["detail"] == "No account with this e-mail."


def test_the_grantable_table_is_built_from_the_session_vocabulary() -> None:
    """One owner of the keys: the surface grants what the PME's session counts, plus the
    ``admin`` row it writes in the form — and nothing typed a second time."""
    table = grantable_roles(APPS)
    assert table == {APP_KEY: SHEMA_APP_ROLES, FORM_APP_KEY: (ADMIN_ROLE, *FORM_DOOR_ROLES)}
    assert "equipe" not in {role for roles in table.values() for role in roles}


# --- regions ----------------------------------------------------------------------------


@pytest.mark.parametrize("role", REGIONAL_ROLES)
@pytest.mark.parametrize("regions", [None, []])
async def test_a_regional_role_without_regions_is_refused(
    db_session, shema_app, form_app, role, regions
) -> None:
    _admin, headers = await make_admin(db_session, shema_app, form_app)
    person = await make_account(db_session, "person@shema.example")

    async with surface_client(db_session) as client:
        res = await client.post(
            GRANTS, json=_grant(person.id, role, regions=regions), headers=headers
        )

    assert res.status_code == 422
    assert res.json()["code"] == "UNPROCESSABLE_VALUE"
    assert "at least one region" in res.json()["detail"]
    assert await _live_roles(db_session, person.id) == []
    assert await _regions(db_session, person.id) == []


async def test_a_regional_role_with_regions_writes_the_scope_rows(
    db_session, shema_app, form_app
) -> None:
    """The rows, who granted them, and what the person's own session now reaches."""
    admin, headers = await make_admin(db_session, shema_app, form_app)
    person = await make_account(db_session, "person@shema.example")

    async with surface_client(db_session) as client:
        res = await client.post(
            GRANTS,
            json=_grant(person.id, "coordinator", regions=["asia", "africa"]),
            headers=headers,
        )
        session = await client.get(SESSION, headers=await auth_header(db_session, person))

    assert res.status_code == 200, res.text
    assert await _live_roles(db_session, person.id) == [(APP_KEY, "coordinator")]
    assert await _regions(db_session, person.id) == [("africa", admin.id), ("asia", admin.id)]
    assert res.json()["regionScope"] == ["africa", "asia"]
    assert session.json()["roles"] == ["coordinator"]
    assert session.json()["regionScope"] == ["africa", "asia"]


async def test_regions_on_a_role_that_is_not_regional_are_refused(
    db_session, shema_app, form_app
) -> None:
    _admin, headers = await make_admin(db_session, shema_app, form_app)
    person = await make_account(db_session, "person@shema.example")

    async with surface_client(db_session) as client:
        res = await client.post(
            GRANTS, json=_grant(person.id, "globalStrategist", regions=["africa"]), headers=headers
        )

    assert res.status_code == 422
    assert "regional role only" in res.json()["detail"]
    assert await _live_roles(db_session, person.id) == []


async def test_a_role_that_is_not_regional_leaves_the_regions_alone(
    db_session, shema_app, form_app
) -> None:
    """``regionKeys: []`` beside ``admin`` is *no regions*, never *reach nothing*: the scope is
    per account, and this coordinator keeps theirs."""
    _admin, headers = await make_admin(db_session, shema_app, form_app)
    person = await make_account(db_session, "person@shema.example", (shema_app, "coordinator"))
    await set_region_scope(db_session, person.id, [ShemaRegionKey.EUROPE])

    async with surface_client(db_session) as client:
        res = await client.post(
            GRANTS, json=_grant(person.id, "admin", regions=[]), headers=headers
        )

    assert res.status_code == 200, res.text
    assert await _regions(db_session, person.id) == [("europe", None)]


async def test_granting_the_role_again_restates_the_regions(
    db_session, shema_app, form_app
) -> None:
    """The regions are the account's whole scope; re-granting a held role is how they move."""
    admin, headers = await make_admin(db_session, shema_app, form_app)
    person = await make_account(db_session, "person@shema.example")

    async with surface_client(db_session) as client:
        await client.post(
            GRANTS, json=_grant(person.id, "obtLab", regions=["africa"]), headers=headers
        )
        res = await client.post(
            GRANTS, json=_grant(person.id, "obtLab", regions=["oceania"]), headers=headers
        )

    assert res.status_code == 200, res.text
    assert await _regions(db_session, person.id) == [("oceania", admin.id)]
    rows = await db_session.execute(select(UserAppRole.id).where(UserAppRole.user_id == person.id))
    assert len(rows.all()) == 1


async def test_revoking_the_last_regional_role_clears_the_regions(
    db_session, shema_app, form_app
) -> None:
    """Left behind, the rows would come back with the next regional grant that states none —
    an approved access request hands out ``resourceCircle`` with no region at all."""
    _admin, headers = await make_admin(db_session, shema_app, form_app)
    person = await make_account(db_session, "person@shema.example")

    async with surface_client(db_session) as client:
        await client.post(
            GRANTS, json=_grant(person.id, "resourceCircle", regions=["europe"]), headers=headers
        )
        res = await client.post(REVOKE, json=_grant(person.id, "resourceCircle"), headers=headers)

    assert res.status_code == 200, res.text
    assert await _live_roles(db_session, person.id) == []
    assert await _regions(db_session, person.id) == []
    assert res.json()["regions"] == []


async def test_revoking_one_of_two_regional_roles_keeps_them(
    db_session, shema_app, form_app
) -> None:
    admin, headers = await make_admin(db_session, shema_app, form_app)
    person = await make_account(db_session, "person@shema.example")

    async with surface_client(db_session) as client:
        await client.post(
            GRANTS, json=_grant(person.id, "coordinator", regions=["asia"]), headers=headers
        )
        await client.post(
            GRANTS, json=_grant(person.id, "obtLab", regions=["asia"]), headers=headers
        )
        res = await client.post(REVOKE, json=_grant(person.id, "obtLab"), headers=headers)

    assert res.status_code == 200, res.text
    assert await _live_roles(db_session, person.id) == [(APP_KEY, "coordinator")]
    assert await _regions(db_session, person.id) == [("asia", admin.id)]


# --- the rules ------------------------------------------------------------------------------


@pytest.mark.parametrize(("held", "wanted"), [("gestor", "mesa"), ("mesa", "gestor")])
async def test_mesa_is_refused_to_a_gestor_and_gestor_to_a_mesa(
    db_session, shema_app, form_app, held, wanted
) -> None:
    _admin, headers = await make_admin(db_session, shema_app, form_app)
    person = await make_account(db_session, "person@shema.example", (form_app, held))

    async with surface_client(db_session) as client:
        res = await client.post(
            GRANTS, json=_grant(person.id, wanted, FORM_APP_KEY), headers=headers
        )

    assert res.status_code == 409
    assert "mutually exclusive" in res.json()["detail"]
    assert await _live_roles(db_session, person.id) == [(FORM_APP_KEY, held)]


async def test_granting_to_yourself_is_refused(db_session, shema_app, form_app) -> None:
    admin, headers = await make_admin(db_session, shema_app, form_app)

    async with surface_client(db_session) as client:
        res = await client.post(GRANTS, json=_grant(admin.id, "globalStrategist"), headers=headers)

    assert res.status_code == 400
    assert res.json()["detail"] == "You cannot grant a role to yourself."
    assert (APP_KEY, "globalStrategist") not in await _live_roles(db_session, admin.id)


async def test_revoking_your_own_role_is_refused(db_session, shema_app, form_app) -> None:
    """The one Admin cannot lock themselves out; another Admin, or an installation admin, can."""
    admin, headers = await make_admin(db_session, shema_app, form_app)

    async with surface_client(db_session) as client:
        res = await client.post(REVOKE, json=_grant(admin.id, "admin"), headers=headers)

    assert res.status_code == 400
    assert res.json()["detail"] == "You cannot revoke your own role."
    assert await _live_roles(db_session, admin.id) == sorted(
        [(APP_KEY, "admin"), (FORM_APP_KEY, "admin")]
    )


async def test_a_refused_grant_leaves_nothing_behind(db_session, shema_app, form_app) -> None:
    """Every refusal comes before the first write. The suite's one session is committed by the
    next token issued — which is exactly what would carry half a grant into the database."""
    _admin, headers = await make_admin(db_session, shema_app, form_app)
    person = await make_account(db_session, "person@shema.example", (form_app, "gestor"))

    async with surface_client(db_session) as client:
        res = await client.post(
            GRANTS, json=_grant(person.id, "mesa", FORM_APP_KEY), headers=headers
        )
    await auth_header(db_session, person)

    assert res.status_code == 409
    assert await _live_roles(db_session, person.id) == [(FORM_APP_KEY, "gestor")]


@pytest.mark.parametrize(
    ("app", "role", "phrase"),
    [
        (FORM_APP_KEY, "equipe", "project membership"),
        (FORM_APP_KEY, "lider", "not a role granted here"),
        ("oral-collector", "admin", "not a role granted here"),
        (APP_KEY, "mesa", "not a role granted here"),
    ],
)
async def test_equipe_lider_and_other_apps_are_not_granted_here(
    db_session, shema_app, form_app, app, role, phrase
) -> None:
    _admin, headers = await make_admin(db_session, shema_app, form_app)
    person = await make_account(db_session, "person@shema.example")

    async with surface_client(db_session) as client:
        res = await client.post(GRANTS, json=_grant(person.id, role, app), headers=headers)

    assert res.status_code == 422
    assert phrase in res.json()["detail"]


async def test_an_unknown_account_is_a_422(db_session, shema_app, form_app) -> None:
    _admin, headers = await make_admin(db_session, shema_app, form_app)

    async with surface_client(db_session) as client:
        res = await client.post(
            GRANTS, json=_grant("no-such-account", "globalStrategist"), headers=headers
        )

    assert res.status_code == 422
    assert res.json()["code"] == "UNKNOWN_REFERENCE"


@pytest.mark.parametrize("revoke_under", [APP_KEY, FORM_APP_KEY])
async def test_the_admin_role_is_granted_and_revoked_in_both_apps(
    db_session, shema_app, form_app, revoke_under
) -> None:
    """One role for two apps: the door reads the ``shema`` row, the form's guards read theirs."""
    _admin, headers = await make_admin(db_session, shema_app, form_app)
    person = await make_account(db_session, "person@shema.example")

    async with surface_client(db_session) as client:
        granted = await client.post(GRANTS, json=_grant(person.id, "admin"), headers=headers)
        assert await _live_roles(db_session, person.id) == [
            (FORM_APP_KEY, "admin"),
            (APP_KEY, "admin"),
        ]
        revoked = await client.post(
            REVOKE, json=_grant(person.id, "admin", revoke_under), headers=headers
        )

    assert granted.status_code == 200, granted.text
    assert revoked.status_code == 200, revoked.text
    assert await _live_roles(db_session, person.id) == []


# --- the history -----------------------------------------------------------------------------


async def test_every_grant_and_revocation_is_in_changes_with_author_and_date(
    db_session, shema_app, form_app
) -> None:
    admin, headers = await make_admin(db_session, shema_app, form_app)
    person = await make_account(db_session, "person@shema.example")

    async with surface_client(db_session) as client:
        await client.post(GRANTS, json=_grant(person.id, "admin"), headers=headers)
        await client.post(REVOKE, json=_grant(person.id, "admin"), headers=headers)
        res = await client.get(CHANGES, headers=headers)

    assert res.status_code == 200, res.text
    about = [entry for entry in res.json() if entry["userId"] == person.id]
    seen = sorted((e["action"], e["appKey"], e["roleKey"]) for e in about)
    assert seen == sorted(
        [
            ("granted", APP_KEY, "admin"),
            ("granted", FORM_APP_KEY, "admin"),
            ("revoked", APP_KEY, "admin"),
            ("revoked", FORM_APP_KEY, "admin"),
        ]
    )
    for entry in about:
        assert entry["actorId"] == admin.id
        assert entry["actorName"] == "The Admin"
        assert entry["actorEmail"] == admin.email
        assert entry["userEmail"] == person.email
        assert entry["at"]


async def test_a_region_move_is_in_changes_with_author_and_date(
    db_session, shema_app, form_app
) -> None:
    """Moving a coordinator between regions writes no role row; the trail is where it shows."""
    admin, headers = await make_admin(db_session, shema_app, form_app)
    person = await make_account(db_session, "person@shema.example")

    async with surface_client(db_session) as client:
        await client.post(
            GRANTS, json=_grant(person.id, "coordinator", regions=["africa"]), headers=headers
        )
        await client.post(
            GRANTS, json=_grant(person.id, "coordinator", regions=["asia"]), headers=headers
        )
        res = await client.get(CHANGES, headers=headers)

    regions = sorted(
        (e["action"], e["regionKey"]) for e in res.json() if e["regionKey"] is not None
    )
    assert regions == [("granted", "africa"), ("granted", "asia"), ("revoked", "africa")]
    for entry in res.json():
        if entry["regionKey"] is not None:
            assert entry["appKey"] == APP_KEY
            assert entry["roleKey"] is None
            assert entry["actorId"] == admin.id
            assert entry["userId"] == person.id
            assert entry["at"]


async def test_changes_leave_out_what_this_surface_does_not_write(
    db_session, shema_app, form_app
) -> None:
    """The ``equipe`` the form hands everybody who registers is nobody's decision."""
    _admin, headers = await make_admin(db_session, shema_app, form_app)
    await make_account(db_session, "registered@shema.example", (form_app, "equipe"))

    async with surface_client(db_session) as client:
        res = await client.get(CHANGES, headers=headers)

    assert all(entry["roleKey"] != "equipe" for entry in res.json())


async def test_changes_are_newest_first_and_capped(db_session, shema_app, form_app) -> None:
    person = await make_account(db_session, "person@shema.example", (shema_app, "coordinator"))
    for regions in ([ShemaRegionKey.AFRICA], [ShemaRegionKey.ASIA], [ShemaRegionKey.EUROPE]):
        await set_region_scope(db_session, person.id, regions)

    everything = await list_grant_changes(db_session, APPS)
    capped = await list_grant_changes(db_session, APPS, limit=2)

    moments = [entry.at for entry in everything]
    assert moments == sorted(moments, reverse=True)
    assert len(everything) == 6
    assert capped == everything[:2]


async def test_the_scope_trail_refuses_update_and_delete(db_session, shema_app) -> None:
    person = await make_account(db_session, "person@shema.example", (shema_app, "coordinator"))
    await set_region_scope(db_session, person.id, [ShemaRegionKey.AFRICA])

    with pytest.raises(DBAPIError):
        await db_session.execute(update(ShemaScopeChange).values(granted=False))
    await db_session.rollback()
    with pytest.raises(DBAPIError):
        await db_session.execute(ShemaScopeChange.__table__.delete())
    await db_session.rollback()


async def test_deleting_the_admin_or_the_account_keeps_rows_and_trail(
    db_session, shema_app, form_app
) -> None:
    """The Admin is the first writer to put a person in ``granted_by``, so deleting that
    account must not be refused by it; and the trail, which has no foreign key on purpose,
    outlives both accounts."""
    admin, headers = await make_admin(db_session, shema_app, form_app)
    person = await make_account(db_session, "person@shema.example")

    async with surface_client(db_session) as client:
        res = await client.post(
            GRANTS, json=_grant(person.id, "coordinator", regions=["africa"]), headers=headers
        )
    assert res.status_code == 200, res.text

    await delete_user(db_session, admin.id)
    assert await _regions(db_session, person.id) == [("africa", None)]

    await delete_user(db_session, person.id)
    trail = await db_session.execute(select(ShemaScopeChange.user_id, ShemaScopeChange.changed_by))
    assert trail.tuples().all() == [(person.id, admin.id)]
