"""The column that stored the conversation's mode leaves, and a downgrade puts it back.

Same constraint as the sibling migration tests: Alembic's full chain does not run on SQLite,
so this exercises the one migration under test. The schema is built from ``Base.metadata`` —
the post-migration shape, with no mode on it — stamped as applied, filled with rows, then
walked down and back up.

The downgrade is written rather than left as a no-op because the migrations job walks the
newest revision down and up again on real Postgres, and because a column dropped without an
inverse is a schema nobody can retreat from. What it cannot put back is the value: the modes
the rows were carrying go with the column, and the restored column holds the same
``calibration_pending`` every row started life with.
"""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

import app.db.models  # noqa: F401  (populates Base.metadata with every table)
from app.core.database import Base
from tests.alembic_harness import columns_of, run_alembic, scalar

REVISION = "20260909_mode01"
PREVIOUS_REVISION = "20260908_arr02"

TABLE = "ir_sessions"
COLUMN = "bridge_mode"
OPENED = "2026-09-09 09:00:00"


async def _build_and_seed(database_url: str) -> str:
    engine = create_async_engine(database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_id = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO ir_sessions (id, pericope, status, messages, after_panorama,"
                " coverage_state, kept_takes, back_translation, created_at, updated_at)"
                " VALUES (:id, 'P01', 'in_progress', '[]', 0, '{}', '{}', '{}', :opened, :opened)"
            ),
            {"id": session_id, "opened": OPENED},
        )
    await engine.dispose()
    return session_id


@pytest.fixture()
async def applied_database(tmp_path) -> dict[str, str]:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'bridge_mode_migration.db'}"
    session_id = await _build_and_seed(database_url)

    stamped = run_alembic(database_url, "stamp", REVISION)
    assert stamped.returncode == 0, stamped.stderr

    return {"url": database_url, "session": session_id}


async def test_no_session_row_has_a_mode_on_it_any_more(applied_database):
    assert COLUMN not in await columns_of(applied_database["url"], TABLE)


async def test_a_downgrade_puts_the_column_back_holding_the_pending_it_started_with(
    applied_database,
):
    url = applied_database["url"]

    down = run_alembic(url, "downgrade", PREVIOUS_REVISION)
    assert down.returncode == 0, down.stderr
    assert COLUMN in await columns_of(url, TABLE)

    stored = await scalar(
        url,
        f"SELECT {COLUMN} FROM {TABLE} WHERE id = :id",
        {"id": applied_database["session"]},
    )
    assert stored == "calibration_pending", (
        "o downgrade não pode devolver o modo que a linha tinha — ele foi embora com a "
        f"coluna; devolve o piso que toda linha começou carregando, e veio {stored!r}"
    )

    up = run_alembic(url, "upgrade", REVISION)
    assert up.returncode == 0, up.stderr
    assert COLUMN not in await columns_of(url, TABLE)


async def test_the_round_trip_keeps_every_session(applied_database):
    url = applied_database["url"]

    assert run_alembic(url, "downgrade", PREVIOUS_REVISION).returncode == 0
    assert run_alembic(url, "upgrade", REVISION).returncode == 0

    assert await scalar(url, f"SELECT count(*) FROM {TABLE}", {}) == 1
