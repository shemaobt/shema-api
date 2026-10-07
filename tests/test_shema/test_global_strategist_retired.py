"""OBT-572: the Global Strategist left — the catalogue, the guards, and the grants it had.

Karina (via Daniel, 6/oct/2026) had meant to retire the *Estrategista Global*; Daniel decided on
7/oct that the accounts holding it **lose** the role rather than being converted. Three things
have to agree: the catalogue no longer names the key (seed, session, the PME's grant surface),
no guard reads it, and ``20261007_shema572`` revokes what installations hold. No migration in
this repository runs under SQLite (``docs/shema.md`` §7.2), so the revision's two callables are
imported from the file and driven against the test connection, the ``test_admin_role.py``
precedent; the CI walk on a clean Postgres matches zero rows, and this file is where the
UPDATE changes one.
"""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select

from app.api.shema._deps import APP_KEY, FORM_APP_KEY
from app.db.models.auth import AccessInvite, Role, UserAppRole
from app.services.shema import GrantApps
from app.services.shema._grant_rules import grantable_roles
from app.services.shema._scope import ROLE_KEYS, ROLE_PRECEDENCE, SHEMA_APP_ROLES
from scripts.seed_apps_roles import seeded_roles
from tests.baker import make_role, make_user, make_user_app_role

RETIRED = "globalStrategist"

_REVISION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "20261007_shema572_retire_global_strategist.py"
)


def _migration():
    spec = importlib.util.spec_from_file_location("_shema572", _REVISION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def _run(db_session, callable_):
    connection = await db_session.connection()
    result = await connection.run_sync(callable_)
    await db_session.commit()
    return result


async def _retired_role(db_session, shema_app) -> Role:
    """The row an installation still has: the seed no longer writes it, so the test does."""
    return await make_role(
        db_session, shema_app.id, role_key=RETIRED, label="Global Strategist", is_system=True
    )


async def _revoked_at(db_session, grant_id: str):
    """Naive, because SQLite hands a stored instant back without its zone."""
    stmt = select(UserAppRole.revoked_at).where(UserAppRole.id == grant_id)
    value = (await db_session.execute(stmt)).scalar_one()
    return value.replace(tzinfo=None) if value is not None else None


# --- the catalogue --------------------------------------------------------------------


def test_the_key_is_gone_from_the_catalogue_the_session_and_the_seed() -> None:
    assert RETIRED not in ROLE_KEYS
    assert RETIRED not in SHEMA_APP_ROLES
    assert RETIRED not in ROLE_PRECEDENCE
    assert RETIRED not in [key for key, _ in seeded_roles(APP_KEY)]
    assert ROLE_KEYS == ("coordinator", "obtLab", "resourceCircle")


def test_the_pme_surface_no_longer_grants_it() -> None:
    """The access screen grants Coordenador, OBT Lab, Resource Circle and Admin — the DoD's
    last line, read off the one owner of what the surface writes."""
    apps = GrantApps(shema=APP_KEY, form=FORM_APP_KEY)

    assert grantable_roles(apps)[APP_KEY] == ("coordinator", "obtLab", "resourceCircle", "admin")


def test_no_guard_in_the_core_names_the_key() -> None:
    """The DoD's first line, as a sweep: nothing under ``app/`` or ``scripts/`` spells the key
    or the role's name in either language."""
    root = Path(__file__).resolve().parents[2]
    needles = ("globalStrategist", "Global Strategist", "Estrategista Global", "GLOBAL_ROLE")
    hits = [
        f"{path.relative_to(root)}: {needle}"
        for folder in ("app", "scripts")
        for path in (root / folder).rglob("*.py")
        for needle in needles
        if needle in path.read_text()
    ]
    assert hits == []


# --- the migration ----------------------------------------------------------------------


def test_the_migration_names_the_app_the_role_and_a_fixed_mark() -> None:
    migration = _migration()

    assert migration.APP_KEY == APP_KEY
    assert migration.ROLE_KEY == RETIRED
    assert migration.down_revision == "20261006_shema567"
    assert isinstance(migration.MARK, datetime) and migration.MARK.tzinfo is not None


async def test_a_live_grant_is_revoked_and_a_revoked_one_is_left_as_it_was(
    db_session, shema_app
) -> None:
    role = await _retired_role(db_session, shema_app)
    holder = await make_user(db_session, email="holder@retired.test")
    former = await make_user(db_session, email="former@retired.test")
    live = await make_user_app_role(db_session, holder.id, shema_app.id, role.id)
    before = datetime(2026, 9, 1)
    already = await make_user_app_role(
        db_session, former.id, shema_app.id, role.id, revoked_at=before
    )

    grants, invites = await _run(db_session, _migration().revoke_global_strategist)

    assert (grants, invites) == (1, 0)
    assert await _revoked_at(db_session, live.id) is not None
    assert await _revoked_at(db_session, already.id) == before


async def test_grants_of_other_roles_and_of_other_apps_are_untouched(
    db_session, shema_app, form_app
) -> None:
    """Guarded by app key **and** role key: a ``coordinator`` here and a ``globalStrategist``
    another product happens to coin are not this revision's business."""
    await _retired_role(db_session, shema_app)
    coordinator = (
        await db_session.execute(
            select(Role).where(Role.app_id == shema_app.id, Role.role_key == "coordinator")
        )
    ).scalar_one()
    elsewhere = await make_role(
        db_session, form_app.id, role_key=RETIRED, label="Elsewhere", is_system=False
    )
    person = await make_user(db_session, email="others@retired.test")
    kept_here = await make_user_app_role(db_session, person.id, shema_app.id, coordinator.id)
    kept_there = await make_user_app_role(db_session, person.id, form_app.id, elsewhere.id)

    grants, _invites = await _run(db_session, _migration().revoke_global_strategist)

    assert grants == 0
    assert await _revoked_at(db_session, kept_here.id) is None
    assert await _revoked_at(db_session, kept_there.id) is None


async def test_a_pending_invite_is_revoked_and_a_spent_or_dead_one_is_left(
    db_session, shema_app
) -> None:
    role = await _retired_role(db_session, shema_app)
    admin = await make_user(db_session, email="admin@retired.test")
    now = datetime.now(UTC)

    def invite(email: str, **state) -> AccessInvite:
        fields = {
            "app_id": shema_app.id,
            "role_id": role.id,
            "email": email,
            "token_hash": f"hash-{email}",
            "expires_at": now + timedelta(days=7),
            "created_by": admin.id,
        }
        return AccessInvite(**{**fields, **state})

    pending = invite("pending@retired.test")
    accepted = invite("accepted@retired.test", accepted_at=now - timedelta(days=1))
    withdrawn = invite("withdrawn@retired.test", revoked_at=now - timedelta(days=2))
    expired = invite("expired@retired.test", expires_at=now - timedelta(days=1))
    db_session.add_all([pending, accepted, withdrawn, expired])
    await db_session.commit()

    _grants, invites = await _run(db_session, _migration().revoke_global_strategist)

    assert invites == 1
    states = {
        row.email: row.revoked_at
        for row in (await db_session.execute(select(AccessInvite))).scalars()
    }
    assert states["pending@retired.test"] is not None
    assert states["accepted@retired.test"] is None
    assert states["expired@retired.test"] is None
    assert states["withdrawn@retired.test"] is not None  # the hand-revocation it already had


async def test_the_downgrade_restores_exactly_what_the_upgrade_stamped(
    db_session, shema_app
) -> None:
    """The handle is the mark: a grant revoked by hand before or after keeps its own instant."""
    role = await _retired_role(db_session, shema_app)
    holder = await make_user(db_session, email="holder2@retired.test")
    former = await make_user(db_session, email="former2@retired.test")
    live = await make_user_app_role(db_session, holder.id, shema_app.id, role.id)
    before = datetime(2026, 9, 1)
    already = await make_user_app_role(
        db_session, former.id, shema_app.id, role.id, revoked_at=before
    )
    migration = _migration()
    await _run(db_session, migration.revoke_global_strategist)

    restored = await _run(db_session, migration.restore_global_strategist)

    assert restored == (1, 0)
    assert await _revoked_at(db_session, live.id) is None
    assert await _revoked_at(db_session, already.id) == before


async def test_an_installation_without_the_row_is_untouched(db_session, shema_app) -> None:
    """A fresh install never had the role row; the revision has nothing to match and invents
    nothing."""
    assert await _run(db_session, _migration().revoke_global_strategist) == (0, 0)
    assert await _run(db_session, _migration().restore_global_strategist) == (0, 0)
