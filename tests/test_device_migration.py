"""ENG-437 — Behaviour 8: the migration that adds the device table is reversible.

Alembic's full chain does not run on SQLite: the first migration in the tree writes a
``DEFAULT now()`` that SQLite rejects. So this exercises the one migration under test
rather than the whole history — the pre-existing schema is built from ``Base.metadata``
the way ``tests/conftest.py`` builds it, stamped at this migration's predecessor, and
filled with rows before the upgrade runs.

The Postgres run is therefore not covered here. What is covered is the shape the issue
asks for: the migration adds a table, and nothing outside that table changes across
upgrade, downgrade and upgrade again.

The issue's own wording — that existing ``device_id`` values in ``ir_questions`` and
``ir_takes`` are untouched — cannot be exercised on this branch, because those tables
arrive with the internalization-room work and are not on ``main``. The general form is
asserted instead.
"""

import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

import app.db.models  # noqa: F401  (populates Base.metadata with every table)
from app.core.database import Base

REPO_ROOT = Path(__file__).resolve().parent.parent
PREVIOUS_REVISION = "20260812_0001"

#: The tip of the device chain, named rather than asked for as "head".
#:
#: While the internalization-room line is unmerged, the two lines both descend from
#: PREVIOUS_REVISION, so the tree has two heads and ``alembic upgrade head`` refuses to
#: guess between them. Naming this one keeps these tests about the device migrations and
#: nothing else. It stops being necessary when the two lines meet on main and this chain
#: rebases onto the room chain's tip — the second head goes away with the rebase.
DEVICE_CHAIN_HEAD = "20260819_0001"

#: Where the rest of the `devices` columns arrive (ENG-448), and what stands between here
#: and there.
#:
#: The rotation and revocation columns were written after ``20260820_merge`` joined the two
#: lines, so their revision descends from the room chain's tip rather than from
#: DEVICE_CHAIN_HEAD. Upgrading straight through would run the room migrations, and one of
#: them inserts a row into `apps` — a table this file never builds, because it stamps the
#: past instead of migrating it. Stamping the room tip is the same move applied to the same
#: kind of thing: migrations that are somebody else's subject.
ROOM_CHAIN_TIP = "20260820_0002"
DEVICE_COLUMNS_HEAD = "20260820_0003"

#: The migration these tests are actually about: the one that creates the table.
DEVICE_TABLE_REVISION = "20260817_0001"
NEW_TABLE = "devices"


def _run_alembic(database_url: str, *argv: str) -> subprocess.CompletedProcess:
    import os

    return subprocess.run(
        [sys.executable, "-m", "alembic", *argv],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "DATABASE_URL": database_url,
            "JWT_SECRET_KEY": "test-secret-for-pytest-only",
            "INNGEST_DEV": "1",
        },
        capture_output=True,
        text=True,
    )


async def _build_schema_without_the_new_table(database_url: str) -> None:
    """The database as it stands before this migration: every table but the new one."""
    engine = create_async_engine(database_url)
    existing = [t for t in Base.metadata.sorted_tables if t.name != NEW_TABLE]
    async with engine.begin() as conn:
        await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn, tables=existing))
    await engine.dispose()


async def _seed_rows(database_url: str) -> str:
    """A project the migration must leave alone. Returns its id."""
    engine = create_async_engine(database_url)
    language_id = str(uuid.uuid4())
    project_id = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO languages (id, name, code) VALUES (:id, :name, :code)"),
            {"id": language_id, "name": "Migration Language", "code": "mig"},
        )
        await conn.execute(
            text(
                "INSERT INTO projects (id, name, language_id, created_at, updated_at)"
                " VALUES (:id, :name, :language_id, :now, :now)"
            ),
            {
                "id": project_id,
                "name": "Migration Project",
                "language_id": language_id,
                "now": "2026-08-17 00:00:00",
            },
        )
    await engine.dispose()
    return project_id


async def _schema_outside_the_new_table(database_url: str) -> set[tuple[str, str, str]]:
    engine = create_async_engine(database_url)
    async with engine.connect() as conn:
        rows = (
            await conn.execute(text("SELECT type, name, COALESCE(sql, '') FROM sqlite_master"))
        ).all()
    await engine.dispose()
    return {
        (kind, name, sql)
        for kind, name, sql in rows
        if NEW_TABLE not in name and NEW_TABLE not in sql and name != "alembic_version"
    }


async def _table_names(database_url: str) -> set[str]:
    engine = create_async_engine(database_url)
    async with engine.connect() as conn:
        rows = (
            await conn.execute(text("SELECT name FROM sqlite_master WHERE type = 'table'"))
        ).all()
    await engine.dispose()
    return {name for (name,) in rows}


async def _project_ids(database_url: str) -> set[str]:
    engine = create_async_engine(database_url)
    async with engine.connect() as conn:
        rows = (await conn.execute(text("SELECT id FROM projects"))).all()
    await engine.dispose()
    return {row_id for (row_id,) in rows}


async def _migrated_shape(database_url: str) -> tuple[set[tuple[str, bool]], set[tuple[str, bool]]]:
    """Columns (name, nullable) and indexes (name, unique) of the migrated new table."""
    engine = create_async_engine(database_url)
    async with engine.connect() as conn:
        columns = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_columns(NEW_TABLE))
        indexes = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_indexes(NEW_TABLE))
    await engine.dispose()
    return (
        {(c["name"], bool(c["nullable"])) for c in columns},
        {(i["name"], bool(i["unique"])) for i in indexes},
    )


@pytest.fixture()
async def stamped_database(tmp_path) -> str:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'migration.db'}"
    await _build_schema_without_the_new_table(database_url)
    await _seed_rows(database_url)

    stamped = _run_alembic(database_url, "stamp", PREVIOUS_REVISION)
    assert stamped.returncode == 0, stamped.stderr

    return database_url


async def test_migration_upgrade_adds_the_table_and_downgrade_removes_it(stamped_database):
    assert NEW_TABLE not in await _table_names(stamped_database)

    up = _run_alembic(stamped_database, "upgrade", DEVICE_CHAIN_HEAD)
    assert up.returncode == 0, up.stderr
    assert NEW_TABLE in await _table_names(stamped_database)

    down = _run_alembic(stamped_database, "downgrade", PREVIOUS_REVISION)
    assert down.returncode == 0, down.stderr
    assert NEW_TABLE not in await _table_names(stamped_database)

    again = _run_alembic(stamped_database, "upgrade", DEVICE_CHAIN_HEAD)
    assert again.returncode == 0, again.stderr
    assert NEW_TABLE in await _table_names(stamped_database)


async def test_migration_round_trip_leaves_everything_outside_the_new_table_unchanged(
    stamped_database,
):
    before = await _schema_outside_the_new_table(stamped_database)

    assert _run_alembic(stamped_database, "upgrade", DEVICE_CHAIN_HEAD).returncode == 0
    after_upgrade = await _schema_outside_the_new_table(stamped_database)

    assert _run_alembic(stamped_database, "downgrade", PREVIOUS_REVISION).returncode == 0
    after_downgrade = await _schema_outside_the_new_table(stamped_database)

    assert _run_alembic(stamped_database, "upgrade", DEVICE_CHAIN_HEAD).returncode == 0
    after_reupgrade = await _schema_outside_the_new_table(stamped_database)

    assert after_upgrade == before
    assert after_downgrade == before
    assert after_reupgrade == before


async def test_migration_round_trip_leaves_existing_rows_intact(stamped_database):
    before = await _project_ids(stamped_database)
    assert before

    assert _run_alembic(stamped_database, "upgrade", DEVICE_CHAIN_HEAD).returncode == 0
    assert _run_alembic(stamped_database, "downgrade", PREVIOUS_REVISION).returncode == 0
    assert _run_alembic(stamped_database, "upgrade", DEVICE_CHAIN_HEAD).returncode == 0

    assert await _project_ids(stamped_database) == before


async def test_migration_builds_the_table_the_model_declares(stamped_database):
    """CLAUDE.md §4 forbids schema changes outside Alembic, which only means anything
    if the migration and the model agree. A model the migration does not build is a
    schema change that happened outside Alembic by omission."""
    assert _run_alembic(stamped_database, "upgrade", DEVICE_CHAIN_HEAD).returncode == 0
    assert _run_alembic(stamped_database, "stamp", ROOM_CHAIN_TIP).returncode == 0
    columns_added = _run_alembic(stamped_database, "upgrade", DEVICE_COLUMNS_HEAD)
    assert columns_added.returncode == 0, columns_added.stderr

    migrated_columns, migrated_indexes = await _migrated_shape(stamped_database)
    model = Base.metadata.tables[NEW_TABLE]

    assert migrated_columns == {(c.name, bool(c.nullable)) for c in model.columns}
    assert migrated_indexes == {(i.name, bool(i.unique)) for i in model.indexes}


async def test_migration_never_names_the_internalization_room_tables():
    """The IR half of the issue's clause, in the only form this branch can assert.

    This migration was written against a branch where ``ir_questions`` and ``ir_takes``
    did not exist, so "their ``device_id`` values are untouched" could not be run at all.
    Where the two lines are joined the tables are present and the assertion is worth more
    than it was: the migration still never names them. The wider claim — that nothing
    outside the new table changes — is what the round-trip test above runs.

    The migration under test is found by its own revision id. Looking for whatever
    descends from ``PREVIOUS_REVISION`` used to identify it and no longer does: the room
    line starts from the same parent, so that search finds two files and neither is
    necessarily this one.
    """
    versions = REPO_ROOT / "alembic" / "versions"
    new_migrations = [
        path
        for path in versions.glob("*.py")
        if f'revision: str = "{DEVICE_TABLE_REVISION}"' in path.read_text()
    ]
    assert len(new_migrations) == 1, f"expected exactly one {DEVICE_TABLE_REVISION}"

    source = new_migrations[0].read_text()
    operative = source.split('"""', 2)[-1]
    for absent in ("ir_questions", "ir_takes", "ir_sessions"):
        assert absent not in operative, f"the migration operates on {absent}"
