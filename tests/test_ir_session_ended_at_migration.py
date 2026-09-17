"""ENG-451 — the column arrives, leaves, comes back, and brings the closed sessions with it.

Same constraint as the sibling migration tests: Alembic's full chain does not run on
SQLite, so this exercises the one migration under test. The schema is built from
``Base.metadata`` — the post-migration shape — stamped as applied, filled with rows, then
walked down and back up.

The backfill is the half worth watching, and it is the reason this migration carries one at
all. A session already closed by the completion floor has no ``ended_at`` — the column did
not exist when it closed — and the rule that reads a session's end derives an *abandonment*
from staleness, never a completion. Left unfilled, every session ever finished would come
back to the Desk as abandoned. What is derivable is ``updated_at``: nothing writes to a
session after the settle that closes it, so the last write is the close.

Nothing is derivable for a session still open or halted, and nothing is invented for one:
those end by the idle rule at read time, where the limit is not yet agreed with the room app
and therefore must not be written into a row.
"""

import os
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

#: This migration and the revision it hangs on — the coverage-events table, which is what
#: a session card's portrait is read out of.
REVISION = "20260820_0003"
PREVIOUS_REVISION = "20260820_0002"

TABLE = "ir_sessions"
OPENED = "2026-08-20 09:00:00"
LAST_WRITE = "2026-08-20 09:34:00"


def _run_alembic(database_url: str, *argv: str) -> subprocess.CompletedProcess:
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
    """One session in each status, all of them closed before the column existed."""
    engine = create_async_engine(database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    ids = {status: str(uuid.uuid4()) for status in ("done", "in_progress", "needs_person")}
    async with engine.begin() as conn:
        for status, session_id in ids.items():
            await conn.execute(
                text(
                    "INSERT INTO ir_sessions (id, pericope, status, messages, after_panorama,"
                    " coverage_state, kept_takes, back_translation, created_at, updated_at)"
                    " VALUES (:id, 'P01', :status, '[]', 0, '{}', '{}', '{}', :opened, :last)"
                ),
                {"id": session_id, "status": status, "opened": OPENED, "last": LAST_WRITE},
            )
    await engine.dispose()
    return ids


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


async def _ended_at(database_url: str, session_id: str) -> object:
    return await _scalar(
        database_url, "SELECT ended_at FROM ir_sessions WHERE id = :id", {"id": session_id}
    )


async def _schema_outside_the_sessions_table(database_url: str) -> set[tuple[str, str, str]]:
    engine = create_async_engine(database_url)
    async with engine.connect() as conn:
        rows = (
            await conn.execute(text("SELECT type, name, COALESCE(sql, '') FROM sqlite_master"))
        ).all()
    await engine.dispose()
    return {
        (kind, name, sql)
        for kind, name, sql in rows
        if name != "alembic_version" and TABLE not in name and TABLE not in sql
    }


@pytest.fixture()
async def applied_database(tmp_path) -> dict[str, str]:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'ended_at_migration.db'}"
    seeded = await _build_and_seed(database_url)

    stamped = _run_alembic(database_url, "stamp", REVISION)
    assert stamped.returncode == 0, stamped.stderr

    return {"url": database_url, **seeded}


async def test_the_column_goes_away_on_downgrade_and_comes_back_on_upgrade(applied_database):
    url = applied_database["url"]

    assert "ended_at" in await _columns(url, TABLE)

    down = _run_alembic(url, "downgrade", PREVIOUS_REVISION)
    assert down.returncode == 0, down.stderr
    assert "ended_at" not in await _columns(url, TABLE)

    up = _run_alembic(url, "upgrade", REVISION)
    assert up.returncode == 0, up.stderr
    assert "ended_at" in await _columns(url, TABLE)


async def test_a_session_already_closed_comes_back_with_the_moment_it_closed(applied_database):
    """Without this every finished session in the field reads as abandoned.

    The rule derives an abandonment from staleness and a completion from a stamp, so a
    ``done`` row with no stamp is a completion the Desk cannot see.
    """
    url = applied_database["url"]

    assert _run_alembic(url, "downgrade", PREVIOUS_REVISION).returncode == 0
    assert _run_alembic(url, "upgrade", REVISION).returncode == 0

    ended_at = await _ended_at(url, applied_database["done"])
    assert ended_at is not None, "a finished session came back with no end"
    assert str(ended_at).startswith("2026-08-20 09:34"), (
        "the close is the session's last write, not the moment the migration ran"
    )


@pytest.mark.parametrize("status", ["in_progress", "needs_person"])
async def test_a_session_that_never_closed_is_left_alone(applied_database, status):
    """The idle limit is not agreed with the room app, so it must not be written into rows."""
    url = applied_database["url"]

    assert _run_alembic(url, "downgrade", PREVIOUS_REVISION).returncode == 0
    assert _run_alembic(url, "upgrade", REVISION).returncode == 0

    assert await _ended_at(url, applied_database[status]) is None


async def test_the_round_trip_keeps_every_session(applied_database):
    url = applied_database["url"]

    assert _run_alembic(url, "downgrade", PREVIOUS_REVISION).returncode == 0
    assert _run_alembic(url, "upgrade", REVISION).returncode == 0

    assert await _scalar(url, f"SELECT count(*) FROM {TABLE}", {}) == 3


async def test_nothing_outside_the_sessions_table_changes(applied_database):
    url = applied_database["url"]
    before = await _schema_outside_the_sessions_table(url)

    assert _run_alembic(url, "downgrade", PREVIOUS_REVISION).returncode == 0
    after_down = await _schema_outside_the_sessions_table(url)

    assert _run_alembic(url, "upgrade", REVISION).returncode == 0
    after_up = await _schema_outside_the_sessions_table(url)

    assert after_down == before
    assert after_up == before
