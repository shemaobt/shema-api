"""ENG-643's migration: the counter that backs the optimistic check on a session's writes.

Same shape as the sibling migration tests: the schema is built from ``Base.metadata``, which
is the post-migration shape, stamped as applied, seeded with a row that never names the new
column, then walked down and back up.

A row seeded before this migration existed named no version either — there was none to
name — so `server_default` is what a pre-migration row picks up rather than a NOT NULL
failure on the next deploy.
"""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

import app.db.models  # noqa: F401  (populates Base.metadata with every table)
from app.core.database import Base
from tests.alembic_harness import columns_of, run_alembic, scalar

pytestmark = pytest.mark.migration

REVISION = "20260916_ver01"
PREVIOUS_REVISION = "20260916_turn01"

TABLE = "ir_sessions"
COLUMN = "version"


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
                " VALUES (:id, 'P01', 'in_progress', '[]', 0, '{}', '{}', '{}',"
                " '2026-09-16 09:00:00', '2026-09-16 09:00:00')"
            ),
            {"id": session_id},
        )
    await engine.dispose()
    return session_id


@pytest.fixture()
async def applied_database(tmp_path) -> dict[str, str]:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'ir_session_version.db'}"
    session_id = await _build_and_seed(database_url)

    stamped = run_alembic(database_url, "stamp", REVISION)
    assert stamped.returncode == 0, stamped.stderr
    return {"url": database_url, "session": session_id}


async def test_the_column_goes_away_on_downgrade_and_comes_back_on_upgrade(applied_database):
    url = applied_database["url"]

    assert COLUMN in await columns_of(url, TABLE)

    down = run_alembic(url, "downgrade", PREVIOUS_REVISION)
    assert down.returncode == 0, down.stderr
    assert COLUMN not in await columns_of(url, TABLE), (
        "o downgrade deixou a coluna para trás, e o upgrade seguinte falha ao recriá-la"
    )

    up = run_alembic(url, "upgrade", REVISION)
    assert up.returncode == 0, up.stderr
    assert COLUMN in await columns_of(url, TABLE)


async def test_a_session_seeded_before_the_migration_starts_at_version_one(applied_database):
    """Uma sessão sem versão nomeada ganha a primeira, não uma coluna nula."""
    url = applied_database["url"]

    assert run_alembic(url, "downgrade", PREVIOUS_REVISION).returncode == 0
    assert run_alembic(url, "upgrade", REVISION).returncode == 0

    where = {"id": applied_database["session"]}
    assert await scalar(url, f"SELECT {COLUMN} FROM {TABLE} WHERE id = :id", where) == 1
    assert await scalar(url, f"SELECT count(*) FROM {TABLE}", {}) == 1
