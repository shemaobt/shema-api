"""OBT-522's Admin: one ``admin`` role in two apps, how it gets there, and who may hand it out.

The role is written two ways and they must agree: ``scripts/seed_apps_roles.py`` for an
installation built from nothing, and ``20260927_shema08`` for one that already has the apps.
No migration in this repository runs under SQLite (``docs/shema.md`` §7.2), so the
revision's two callables are imported from the file and driven against the test connection,
the way Alembic drives them against a real one — the ENG-373 precedent. The CI walk on a
clean Postgres only ever takes the *skip* branch, because the apps are not there; this file
is the only place the insert runs.

**Seeding the role opened a door this file also keeps shut.** The form's two access doors
grant any role the app has, and the Gestor may use them; with an ``admin`` row in the form a
Gestor could name an Admin, who passes the shared ``assert_can_manage_roles`` and revokes
through ``/api/roles``. ``resource_request_access`` now refuses that to all but an
installation admin, and the refusals are asserted here, beside the seed that made them
necessary.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import select

from app.api.shema._deps import APP_KEY, FORM_APP_KEY
from app.core.exceptions import AuthorizationError
from app.db.models.auth import AccessInvite, App, Role, UserAppRole
from app.services.authorization import assert_can_manage_roles
from app.services.resource_request_access import create_invite, grant_access
from app.services.shema._scope import ADMIN_ROLE
from scripts.seed_apps_roles import (
    PLATFORM_ADMIN_APPS,
    PLATFORM_ADMIN_LABEL,
    SEED_APPS,
    seeded_roles,
)
from tests.baker import make_app, make_role, make_user
from tests.test_shema.conftest import grant

_REVISION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "20260927_shema08_platform_admin_role.py"
)


def _migration():
    spec = importlib.util.spec_from_file_location("_shema08", _REVISION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def _run(db_session, callable_) -> None:
    connection = await db_session.connection()
    await connection.run_sync(callable_)
    await db_session.commit()


async def _admin_labels(db_session) -> dict[str, str]:
    """``{app_key: label}`` of every ``admin`` row, read by column so no cached object hides a
    change the migration made underneath the session."""
    stmt = (
        select(App.app_key, Role.label)
        .join(Role, Role.app_id == App.id)
        .where(Role.role_key == ADMIN_ROLE)
    )
    return dict((await db_session.execute(stmt)).tuples().all())


# --- the seed ------------------------------------------------------------------------


def test_the_seed_gives_both_apps_the_admin_role_under_its_platform_label() -> None:
    assert set(PLATFORM_ADMIN_APPS) == {APP_KEY, FORM_APP_KEY}
    for app_key in PLATFORM_ADMIN_APPS:
        assert (ADMIN_ROLE, "Admin da plataforma") in seeded_roles(app_key), app_key
        assert [key for key, _ in seeded_roles(app_key)].count(ADMIN_ROLE) == 1


def test_the_seed_keeps_the_forms_own_roles_beside_the_admin() -> None:
    """The form's four ids stay exactly its frontend's; the Admin is added beside them."""
    keys = [key for key, _ in seeded_roles(FORM_APP_KEY)]
    assert keys == ["equipe", "mesa", "gestor", "lider", ADMIN_ROLE]


def test_every_other_app_keeps_its_admin_label() -> None:
    """Six products seed an ``admin`` of their own; the platform label is not theirs."""
    others = [key for key, *_ in SEED_APPS if key not in PLATFORM_ADMIN_APPS]
    with_admin = [key for key in others if any(k == ADMIN_ROLE for k, _ in seeded_roles(key))]
    assert with_admin, "no other app seeds an admin — the check below proves nothing"
    for app_key in with_admin:
        assert (ADMIN_ROLE, "Admin") in seeded_roles(app_key), app_key


# --- the migration --------------------------------------------------------------------


def test_the_migration_names_the_seeds_key_label_and_apps() -> None:
    """The two writers of one row. A label corrected in one and not the other would show two
    names for one role depending on how the installation was built."""
    migration = _migration()

    assert migration.ROLE_KEY == ADMIN_ROLE
    assert migration.LABEL == PLATFORM_ADMIN_LABEL
    assert set(migration.APP_KEYS) == set(PLATFORM_ADMIN_APPS)


async def test_the_migration_seeds_admin_in_both_apps(db_session) -> None:
    await make_app(db_session, app_key=APP_KEY, name="Shemá")
    await make_app(db_session, app_key=FORM_APP_KEY, name="Resource Request Form")

    await _run(db_session, _migration().seed_admin_role)

    assert await _admin_labels(db_session) == {
        APP_KEY: "Admin da plataforma",
        FORM_APP_KEY: "Admin da plataforma",
    }
    systems = select(Role.is_system).where(Role.role_key == ADMIN_ROLE)
    assert set((await db_session.execute(systems)).scalars()) == {True}


async def test_the_migration_relabels_an_existing_admin_and_is_idempotent(db_session) -> None:
    """A row already there — written by hand, under another label — ends under the platform
    label, and a second run changes nothing."""
    shema = await make_app(db_session, app_key=APP_KEY, name="Shemá")
    await make_app(db_session, app_key=FORM_APP_KEY, name="Resource Request Form")
    await make_role(db_session, shema.id, role_key=ADMIN_ROLE, label="Admin", is_system=False)

    await _run(db_session, _migration().seed_admin_role)
    await _run(db_session, _migration().seed_admin_role)

    count = select(Role.id).where(Role.role_key == ADMIN_ROLE)
    assert len((await db_session.execute(count)).all()) == 2
    assert set((await _admin_labels(db_session)).values()) == {"Admin da plataforma"}


async def test_the_migration_skips_an_app_that_is_not_registered(db_session) -> None:
    """The seed creates app and role together; the revision only reaches apps that exist."""
    await make_app(db_session, app_key=APP_KEY, name="Shemá")

    await _run(db_session, _migration().seed_admin_role)

    assert await _admin_labels(db_session) == {APP_KEY: "Admin da plataforma"}


async def test_the_downgrade_removes_the_role_and_every_grant_of_it(db_session) -> None:
    """Undoing the role is undoing who holds it — the foreign keys cascade, and another app's
    ``admin`` is not touched."""
    shema = await make_app(db_session, app_key=APP_KEY, name="Shemá")
    await make_app(db_session, app_key=FORM_APP_KEY, name="Resource Request Form")
    other = await make_app(db_session, app_key="tripod-studio", name="Tripod Studio")
    await make_role(db_session, other.id, role_key=ADMIN_ROLE, label="Admin", is_system=True)
    await _run(db_session, _migration().seed_admin_role)
    holder = await make_user(db_session, email="holder@admin.test")
    await grant(db_session, holder, shema, ADMIN_ROLE)

    await _run(db_session, _migration().drop_admin_role)

    assert await _admin_labels(db_session) == {"tripod-studio": "Admin"}
    grants = select(UserAppRole.id).where(UserAppRole.user_id == holder.id)
    assert (await db_session.execute(grants)).all() == []


# --- what the role carries, and who may hand it out -----------------------------------


async def test_an_admin_holder_may_manage_that_apps_roles(db_session, shema_app) -> None:
    """The platform's shared predicate reads an app's ``admin`` role — which is why naming one
    is guarded below. Since OBT-543 the Admin concedes through ``/api/shema/access``, and the
    raw ``/api/roles/assign`` and ``/revoke`` refuse the two apps to anyone but an installation
    admin (``test_admin_gate.py``); ``/api/roles/check`` still reads this predicate."""
    admin = await make_user(db_session, email="manager@admin.test")
    await grant(db_session, admin, shema_app, ADMIN_ROLE)

    await assert_can_manage_roles(db_session, admin, APP_KEY)


async def test_a_gestor_cannot_name_an_admin_in_the_form(db_session, form_app) -> None:
    gestor = await make_user(db_session, email="gestor-names@admin.example")
    await grant(db_session, gestor, form_app, "gestor")
    target = await make_user(db_session, email="target@admin.example")

    with pytest.raises(AuthorizationError):
        await grant_access(db_session, gestor, target.id, FORM_APP_KEY, ADMIN_ROLE)

    held = select(UserAppRole.id).where(UserAppRole.user_id == target.id)
    assert (await db_session.execute(held)).all() == []


async def test_a_gestor_cannot_invite_an_admin_to_the_form(db_session, form_app) -> None:
    gestor = await make_user(db_session, email="gestor-invites@admin.example")
    await grant(db_session, gestor, form_app, "gestor")

    with pytest.raises(AuthorizationError):
        await create_invite(db_session, gestor, FORM_APP_KEY, "someone@admin.example", ADMIN_ROLE)

    assert (await db_session.execute(select(AccessInvite.id))).all() == []


async def test_a_gestor_still_grants_the_forms_own_roles(db_session, form_app) -> None:
    """The refusal is about one key; the Gestor's concession of the rest is unchanged."""
    gestor = await make_user(db_session, email="gestor-mesa@admin.example")
    await grant(db_session, gestor, form_app, "gestor")
    target = await make_user(db_session, email="new-equipe@admin.example")

    assignment = await grant_access(db_session, gestor, target.id, FORM_APP_KEY, "equipe")

    assert assignment.user_id == target.id


async def test_an_installation_admin_can_still_name_an_admin_in_the_form(
    db_session, form_app
) -> None:
    installation = await make_user(
        db_session, email="installation@admin.example", is_platform_admin=True
    )
    target = await make_user(db_session, email="named@admin.example")

    assignment = await grant_access(db_session, installation, target.id, FORM_APP_KEY, ADMIN_ROLE)

    assert assignment.user_id == target.id
