"""ENG-440 — Behaviour 5: the migration is reversible on tables that already hold rows.

Same constraint as the device migrations: Alembic's full chain does not run on SQLite, so
this exercises the one migration under test. The schema is built from ``Base.metadata`` —
which is the post-migration shape — stamped as applied, filled with rows, and then walked
down and back up.

That order matters for the half that is not just "a column appears". ``ir_takes.team_id``
is being renamed, not added, so the thing worth proving is that going down restores the
old name **with the values still in it**, and coming back up puts them under the new name
again. A rename that quietly drops a column would pass a test that only counted columns.
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

#: This migration and the revision it sits on. The parent is the merge revision that
#: joins the room and device lines: stepping back from a merge revision is ambiguous, so
#: the merge is never a head and this migration is always the thing above it. Both go
#: away when the two lines meet on main.
REVISION = "20260820_0001"
PREVIOUS_REVISION = "20260820_merge"

CARRYING_TABLES = ("ir_sessions", "ir_questions", "ir_takes")


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


async def _build_and_seed(database_url: str) -> dict[str, str]:
    """Every table, with one row per carrying table already holding a project."""
    engine = create_async_engine(database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    project_id = str(uuid.uuid4())
    ids = {table: str(uuid.uuid4()) for table in CARRYING_TABLES}
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO ir_sessions (id, pericope, status, messages, after_panorama,"
                " coverage_state, kept_takes, back_translation, project_id, created_at,"
                " updated_at) VALUES (:id, 'OV', 'in_progress', '[]', 0, '{}', '{}', '{}',"
                " :project_id, :now, :now)"
            ),
            {"id": ids["ir_sessions"], "project_id": project_id, "now": "2026-08-20 00:00:00"},
        )
        await conn.execute(
            text(
                "INSERT INTO ir_questions (id, device_id, session_id, pericope, audio_key,"
                " status, project_id, created_at) VALUES (:id, 'dev', :session, 'OV', 'k',"
                " 'open', :project_id, :now)"
            ),
            {
                "id": ids["ir_questions"],
                "session": ids["ir_sessions"],
                "project_id": project_id,
                "now": "2026-08-20 00:00:00",
            },
        )
        await conn.execute(
            text(
                "INSERT INTO ir_takes (id, session_id, device_id, project_id, pericope, kind,"
                " scope, storage_key, size_bytes, sha256, crc32c, content_type, created_at)"
                " VALUES (:id, :session, 'dev', :project_id, 'OV', 'ensaio', 'OV', 'key', 1,"
                " 'sha', 'crc', 'audio/m4a', :now)"
            ),
            {
                "id": ids["ir_takes"],
                "session": ids["ir_sessions"],
                "project_id": project_id,
                "now": "2026-08-20 00:00:00",
            },
        )
    await engine.dispose()
    return {"project_id": project_id, **ids}


async def _indexes(database_url: str, table: str) -> set[str]:
    engine = create_async_engine(database_url)
    async with engine.connect() as conn:
        indexes = await conn.run_sync(lambda sync: inspect(sync).get_indexes(table))
    await engine.dispose()
    return {i["name"] for i in indexes}


async def _columns(database_url: str, table: str) -> set[str]:
    engine = create_async_engine(database_url)
    async with engine.connect() as conn:
        columns = await conn.run_sync(lambda sync: inspect(sync).get_columns(table))
    await engine.dispose()
    return {c["name"] for c in columns}


async def _scalar(database_url: str, sql: str, params: dict) -> object:
    engine = create_async_engine(database_url)
    async with engine.connect() as conn:
        value = (await conn.execute(text(sql), params)).scalar_one_or_none()
    await engine.dispose()
    return value


async def _schema_outside_the_carrying_tables(database_url: str) -> set[tuple[str, str, str]]:
    engine = create_async_engine(database_url)
    async with engine.connect() as conn:
        rows = (
            await conn.execute(text("SELECT type, name, COALESCE(sql, '') FROM sqlite_master"))
        ).all()
    await engine.dispose()
    return {
        (kind, name, sql)
        for kind, name, sql in rows
        if name != "alembic_version" and not any(t in name or t in sql for t in CARRYING_TABLES)
    }


@pytest.fixture()
async def applied_database(tmp_path) -> dict[str, str]:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'ir_migration.db'}"
    seeded = await _build_and_seed(database_url)

    stamped = _run_alembic(database_url, "stamp", REVISION)
    assert stamped.returncode == 0, stamped.stderr

    return {"url": database_url, **seeded}


async def test_downgrade_restores_team_id_with_its_values_and_upgrade_puts_them_back(
    applied_database,
):
    url = applied_database["url"]
    take_id = applied_database["ir_takes"]
    project_id = applied_database["project_id"]

    assert "project_id" in await _columns(url, "ir_takes")

    down = _run_alembic(url, "downgrade", PREVIOUS_REVISION)
    assert down.returncode == 0, down.stderr

    after_down = await _columns(url, "ir_takes")
    assert "team_id" in after_down
    assert "project_id" not in after_down
    assert (
        await _scalar(url, "SELECT team_id FROM ir_takes WHERE id = :id", {"id": take_id})
        == project_id
    ), "the rename lost the values on the way down"

    up = _run_alembic(url, "upgrade", REVISION)
    assert up.returncode == 0, up.stderr

    after_up = await _columns(url, "ir_takes")
    assert "project_id" in after_up
    assert "team_id" not in after_up
    assert (
        await _scalar(url, "SELECT project_id FROM ir_takes WHERE id = :id", {"id": take_id})
        == project_id
    ), "the rename lost the values on the way back up"


@pytest.mark.parametrize("table", ["ir_sessions", "ir_questions"])
async def test_the_added_columns_go_away_on_downgrade_and_come_back_on_upgrade(
    applied_database, table
):
    url = applied_database["url"]

    assert "project_id" in await _columns(url, table)

    assert _run_alembic(url, "downgrade", PREVIOUS_REVISION).returncode == 0
    assert "project_id" not in await _columns(url, table)

    assert _run_alembic(url, "upgrade", REVISION).returncode == 0
    assert "project_id" in await _columns(url, table)


async def test_the_round_trip_keeps_the_rows_in_the_carrying_tables(applied_database):
    url = applied_database["url"]

    assert _run_alembic(url, "downgrade", PREVIOUS_REVISION).returncode == 0
    assert _run_alembic(url, "upgrade", REVISION).returncode == 0

    for table in CARRYING_TABLES:
        surviving = await _scalar(url, f"SELECT count(*) FROM {table}", {})
        assert surviving == 1, f"{table} lost its row across the round trip"


async def test_nothing_outside_the_carrying_tables_changes(applied_database):
    url = applied_database["url"]
    before = await _schema_outside_the_carrying_tables(url)

    assert _run_alembic(url, "downgrade", PREVIOUS_REVISION).returncode == 0
    after_down = await _schema_outside_the_carrying_tables(url)

    assert _run_alembic(url, "upgrade", REVISION).returncode == 0
    after_up = await _schema_outside_the_carrying_tables(url)

    assert after_down == before
    assert after_up == before


@pytest.mark.parametrize("table", CARRYING_TABLES)
async def test_the_migration_creates_the_index_the_query_plan_needs(applied_database, table):
    """The index has to come from the migration, not from the model.

    Every other test here builds the schema from Base.metadata, where ``index=True``
    creates it for free — so a migration that forgot the index would leave all of them
    green and only production would notice, as a sequential scan on a growing table.
    Walking down and back up is what makes this the migration's index and nobody else's.
    """
    url = applied_database["url"]
    expected = f"ix_{table}_project_id"

    assert _run_alembic(url, "downgrade", PREVIOUS_REVISION).returncode == 0
    assert expected not in await _indexes(url, table)

    assert _run_alembic(url, "upgrade", REVISION).returncode == 0
    assert expected in await _indexes(url, table), (
        f"{table} came back without {expected}; a query by project would scan the table"
    )
