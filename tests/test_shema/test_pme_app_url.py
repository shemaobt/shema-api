"""OBT-567: the PME's ``app_url`` is the address it answers on, written two ways that agree.

``scripts/seed_apps_roles.py`` writes it for an installation built from nothing, and
``20261006_shema567`` corrects the row of one that already holds BE-03's conventional hostname
— which never got a DNS record, so the reset e-mail ``request_password_reset`` builds from the
column led nowhere. No migration in this repository runs under SQLite (``docs/shema.md`` §7.2),
so the revision's callable is imported from the file and driven against the test connection,
the ``test_admin_role.py`` precedent. The CI walk on a clean Postgres only ever matches zero
rows, because the apps are not there; this file is the only place the UPDATE changes one.

The guard is the point of the migration and gets a case of its own: a row somebody already
corrected by hand must be left exactly as they left it.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from sqlalchemy import select, update

from app.api.shema._deps import APP_KEY
from app.db.models.auth import App
from scripts.seed_apps_roles import SEED_APPS
from tests.baker import make_app

_REVISION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "20261006_shema567_pme_app_url.py"
)

PME_ADDRESS = "https://project-management-ecosystem-f7ssqjozfq-uc.a.run.app"
RETIRED_HOSTNAME = "https://shema.shemaywam.com"


def _migration():
    spec = importlib.util.spec_from_file_location("_shema567", _REVISION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def _run(db_session, callable_) -> int:
    connection = await db_session.connection()
    changed = await connection.run_sync(callable_)
    await db_session.commit()
    return changed


async def _app_url(db_session, app_key: str) -> str | None:
    """Read by column, so no cached object hides a change the migration made underneath."""
    stmt = select(App.app_url).where(App.app_key == app_key)
    return (await db_session.execute(stmt)).scalar_one_or_none()


async def _register(db_session, app_key: str, app_url: str) -> None:
    app = await make_app(db_session, app_key=app_key, name=app_key)
    await db_session.execute(update(App).where(App.id == app.id).values(app_url=app_url))
    await db_session.commit()


# --- the seed ------------------------------------------------------------------------


def test_the_seed_carries_the_address_the_pme_answers_on() -> None:
    entry = next(row for row in SEED_APPS if row[0] == APP_KEY)
    assert entry[2] == PME_ADDRESS


def test_the_migration_names_the_seeds_app_and_address() -> None:
    """Two writers of one cell. A seed moved to a new host without the migration following
    would leave fresh and installed databases pointing at two different PMEs."""
    migration = _migration()

    assert migration.APP_KEY == APP_KEY
    assert migration.NEW_URL == PME_ADDRESS
    assert migration.OLD_URL == RETIRED_HOSTNAME
    assert migration.down_revision == "20261004_meet02"


# --- the migration --------------------------------------------------------------------


async def test_a_row_still_on_the_retired_hostname_is_pointed_at_the_pme(db_session) -> None:
    await _register(db_session, APP_KEY, RETIRED_HOSTNAME)

    changed = await _run(db_session, _migration().point_pme_at_its_address)

    assert changed == 1
    assert await _app_url(db_session, APP_KEY) == PME_ADDRESS


async def test_a_row_already_corrected_by_hand_is_left_as_it_was(db_session) -> None:
    """The guard. Staging is the likely case: whoever fixed it may have chosen a value this
    file does not know, and the migration must not overwrite a correction with its own."""
    by_hand = "https://pme.example.org"
    await _register(db_session, APP_KEY, by_hand)

    changed = await _run(db_session, _migration().point_pme_at_its_address)

    assert changed == 0
    assert await _app_url(db_session, APP_KEY) == by_hand


async def test_other_apps_on_the_retired_hostname_are_not_the_migrations_business(
    db_session,
) -> None:
    """Keyed by app as well as by value: the hostname alone is not what identifies the row."""
    await _register(db_session, "another-app", RETIRED_HOSTNAME)

    changed = await _run(db_session, _migration().point_pme_at_its_address)

    assert changed == 0
    assert await _app_url(db_session, "another-app") == RETIRED_HOSTNAME


async def test_an_installation_without_the_pme_row_is_untouched(db_session) -> None:
    """The seed writes the right value when it registers the app; the migration has no row to
    correct and must not invent one."""
    changed = await _run(db_session, _migration().point_pme_at_its_address)

    assert changed == 0
    assert await _app_url(db_session, APP_KEY) is None


async def test_running_it_twice_changes_nothing_the_second_time(db_session) -> None:
    await _register(db_session, APP_KEY, RETIRED_HOSTNAME)

    assert await _run(db_session, _migration().point_pme_at_its_address) == 1
    assert await _run(db_session, _migration().point_pme_at_its_address) == 0
    assert await _app_url(db_session, APP_KEY) == PME_ADDRESS
