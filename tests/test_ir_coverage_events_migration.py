"""ENG-445 — Behaviours 6 and 7: the table arrives, leaves and comes back, and says what
it could not derive.

Same constraint as the sibling migration tests: Alembic's full chain does not run on
SQLite, so this exercises the one migration under test. The schema is built from
``Base.metadata`` — the post-migration shape — stamped as applied, filled with rows, then
walked down and back up.

The backfill is the half worth watching. A session that already exists has a
`coverage_state` and nothing else: the beads it ended on are derivable, and the moment
each one moved is not. So the round trip has to bring back the terminal step of every
bead above `not_encountered`, and has to *not* bring back a `surfaced` step for a bead
that ended `engaged` — that step may never have been classified separately, and inventing
it would put a transition in the history that no one can point at.
"""

import json
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

#: This migration and the revision it hangs on. That parent is the room's `project_id`
#: migration, which is what gives a session the project an event carries.
REVISION = "20260820_0002"
PREVIOUS_REVISION = "20260820_0001"

TABLE = "ir_coverage_events"
WHEN = "2026-08-20 00:00:00"


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


WORKED = {"being:B3": "engaged", "place:the-road": "surfaced", "scene:1": "not_encountered"}
PANORAMA: dict[str, str] = {}


async def _build_and_seed(database_url: str) -> dict[str, str]:
    engine = create_async_engine(database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    ids = {"worked": str(uuid.uuid4()), "panorama": str(uuid.uuid4())}
    project_id = str(uuid.uuid4())
    async with engine.begin() as conn:
        for name, pericope, coverage in (
            ("worked", "P03", WORKED),
            ("panorama", "OV-Ruth", PANORAMA),
        ):
            await conn.execute(
                text(
                    "INSERT INTO ir_sessions (id, pericope, status, messages, after_panorama,"
                    " coverage_state, kept_takes, back_translation, project_id, created_at,"
                    " updated_at) VALUES (:id, :pericope, 'done', '[]', 0, :coverage, '{}',"
                    " '{}', :project_id, :now, :now)"
                ),
                {
                    "id": ids[name],
                    "pericope": pericope,
                    "coverage": json.dumps(coverage),
                    "project_id": project_id,
                    "now": WHEN,
                },
            )
        await conn.execute(
            text(
                f"INSERT INTO {TABLE} (id, session_id, project_id, pericope, element_key,"
                " status, at) VALUES (:id, :session, :project_id, 'P03', 'being:B3',"
                " 'surfaced', :now)"
            ),
            {
                "id": str(uuid.uuid4()),
                "session": ids["worked"],
                "project_id": project_id,
                "now": WHEN,
            },
        )
    await engine.dispose()
    return {"project_id": project_id, **ids}


async def _rows(database_url: str, sql: str, params: dict | None = None) -> list[tuple]:
    engine = create_async_engine(database_url)
    async with engine.connect() as conn:
        rows = (await conn.execute(text(sql), params or {})).all()
    await engine.dispose()
    return [tuple(row) for row in rows]


async def _tables(database_url: str) -> set[str]:
    engine = create_async_engine(database_url)
    async with engine.connect() as conn:
        names = await conn.run_sync(lambda sync: set(inspect(sync).get_table_names()))
    await engine.dispose()
    return names


async def _indexes(database_url: str, table: str) -> set[str]:
    engine = create_async_engine(database_url)
    async with engine.connect() as conn:
        indexes = await conn.run_sync(lambda sync: inspect(sync).get_indexes(table))
    await engine.dispose()
    return {index["name"] for index in indexes}


async def _unique_constraints(database_url: str, table: str) -> set[str]:
    engine = create_async_engine(database_url)
    async with engine.connect() as conn:
        constraints = await conn.run_sync(lambda sync: inspect(sync).get_unique_constraints(table))
    await engine.dispose()
    return {constraint["name"] for constraint in constraints}


async def _schema_outside_the_events_table(database_url: str) -> set[tuple[str, str, str]]:
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
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'ir_coverage_events.db'}"
    seeded = await _build_and_seed(database_url)

    stamped = _run_alembic(database_url, "stamp", REVISION)
    assert stamped.returncode == 0, stamped.stderr

    return {"url": database_url, **seeded}


async def test_the_table_goes_away_on_downgrade_and_comes_back_on_upgrade(applied_database):
    """Behaviour 7."""
    url = applied_database["url"]
    assert TABLE in await _tables(url)

    down = _run_alembic(url, "downgrade", PREVIOUS_REVISION)
    assert down.returncode == 0, down.stderr
    assert TABLE not in await _tables(url)

    up = _run_alembic(url, "upgrade", REVISION)
    assert up.returncode == 0, up.stderr
    assert TABLE in await _tables(url)


async def test_the_round_trip_leaves_the_sessions_alone(applied_database):
    """Behaviour 7 — the rows the events describe survive the trip."""
    url = applied_database["url"]

    assert _run_alembic(url, "downgrade", PREVIOUS_REVISION).returncode == 0
    assert _run_alembic(url, "upgrade", REVISION).returncode == 0

    assert await _rows(url, "SELECT count(*) FROM ir_sessions") == [(2,)]


async def test_nothing_outside_the_events_table_changes(applied_database):
    url = applied_database["url"]
    before = await _schema_outside_the_events_table(url)

    assert _run_alembic(url, "downgrade", PREVIOUS_REVISION).returncode == 0
    after_down = await _schema_outside_the_events_table(url)

    assert _run_alembic(url, "upgrade", REVISION).returncode == 0
    after_up = await _schema_outside_the_events_table(url)

    assert after_down == before
    assert after_up == before


async def test_the_backfill_derives_the_beads_that_are_derivable(applied_database):
    """Behaviour 6 — what the state proves, the history gets."""
    url = applied_database["url"]

    assert _run_alembic(url, "downgrade", PREVIOUS_REVISION).returncode == 0
    assert _run_alembic(url, "upgrade", REVISION).returncode == 0

    derived = await _rows(
        url,
        f"SELECT element_key, status FROM {TABLE} WHERE session_id = :session ORDER BY element_key",
        {"session": applied_database["worked"]},
    )

    assert derived == [("being:B3", "engaged"), ("place:the-road", "surfaced")]


async def test_the_backfill_does_not_invent_the_steps_it_cannot_see(applied_database):
    """Behaviour 6 — an engaged bead gets one row, not a surfaced step it never proved.

    The `surfaced` event seeded before the downgrade is gone for good, and that is the
    honest answer: `coverage_state` records where a bead ended, never how it got there.
    """
    url = applied_database["url"]

    assert _run_alembic(url, "downgrade", PREVIOUS_REVISION).returncode == 0
    assert _run_alembic(url, "upgrade", REVISION).returncode == 0

    assert await _rows(
        url,
        f"SELECT count(*) FROM {TABLE} WHERE element_key = 'being:B3' AND status = 'surfaced'",
    ) == [(0,)]


async def test_the_backfill_leaves_untouched_beads_out(applied_database):
    """Behaviour 6 — `not_encountered` is the absence of a transition, not one."""
    url = applied_database["url"]

    assert _run_alembic(url, "downgrade", PREVIOUS_REVISION).returncode == 0
    assert _run_alembic(url, "upgrade", REVISION).returncode == 0

    assert await _rows(url, f"SELECT count(*) FROM {TABLE} WHERE status = 'not_encountered'") == [
        (0,)
    ]
    assert await _rows(
        url,
        f"SELECT count(*) FROM {TABLE} WHERE session_id = :session",
        {"session": applied_database["panorama"]},
    ) == [(0,)]


async def test_the_backfill_carries_the_project_and_the_passage(applied_database):
    """Behaviour 6 — an event that cannot say whose bead it was cannot answer Behaviour 5."""
    url = applied_database["url"]

    assert _run_alembic(url, "downgrade", PREVIOUS_REVISION).returncode == 0
    assert _run_alembic(url, "upgrade", REVISION).returncode == 0

    assert await _rows(
        url,
        f"SELECT count(*) FROM {TABLE} e JOIN ir_sessions s ON s.id = e.session_id"
        " WHERE e.project_id IS NOT s.project_id OR e.pericope IS NOT s.pericope"
        " OR e.at IS NOT s.updated_at",
    ) == [(0,)], "the backfilled rows disagree with the sessions they were derived from"


async def test_the_migration_creates_the_indexes_the_query_plans_need(applied_database):
    """The indexes have to come from the migration, not from the model.

    Every other test here builds the schema from `Base.metadata`, where the model's own
    indexes come for free — so a migration that forgot them would leave all of these green
    and only production would notice, as a sequential scan on the one table in the room
    that grows without bound.
    """
    url = applied_database["url"]

    assert _run_alembic(url, "downgrade", PREVIOUS_REVISION).returncode == 0
    assert _run_alembic(url, "upgrade", REVISION).returncode == 0

    assert "ix_ir_coverage_events_element_touched" in await _indexes(url, TABLE)
    assert "uq_ir_coverage_events_step" in await _unique_constraints(url, TABLE)
