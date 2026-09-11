"""ENG-869's migration: the count on the stretch row, and the table that keeps a crossing.

Walked down and back up rather than only inspected, because a migration that creates the shape
and cannot undo it is a migration nobody can deploy behind.
"""

from __future__ import annotations

import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

import app.db.models  # noqa: F401  (populates Base.metadata with every table)
from app.core.database import Base
from tests.test_ir_project_id_migration import _columns, _run_alembic

REVISION = "20260910_hard01"
PREVIOUS_REVISION = "20260910_meet01"


async def _tables(database_url: str) -> set[str]:
    engine = create_async_engine(database_url)
    async with engine.connect() as conn:
        names = await conn.run_sync(lambda sync: inspect(sync).get_table_names())
    await engine.dispose()
    return set(names)


@pytest.fixture()
async def hard_stretch_database(tmp_path) -> str:
    """The post-migration schema, stamped as applied, ready to walk down and back up.

    Alembic's full chain does not run on SQLite, so the shape is the neighbours': build from
    `Base.metadata`, which is the post-migration schema, and stamp it as applied.
    """
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'ir_hard_stretches.db'}"
    engine = create_async_engine(database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()

    stamped = _run_alembic(database_url, "stamp", REVISION)
    assert stamped.returncode == 0, stamped.stderr
    return database_url


async def test_the_migration_adds_the_count_and_the_mark_table(
    hard_stretch_database: str,
) -> None:
    url = hard_stretch_database

    assert "tellings" in await _columns(url, "ir_segments")
    assert await _tables(url) >= {"ir_hard_stretches"}

    down = _run_alembic(url, "downgrade", PREVIOUS_REVISION)
    assert down.returncode == 0, down.stderr
    assert "tellings" not in await _columns(url, "ir_segments")
    assert "ir_hard_stretches" not in await _tables(url)

    up = _run_alembic(url, "upgrade", REVISION)
    assert up.returncode == 0, up.stderr
    assert "tellings" in await _columns(url, "ir_segments")
    assert await _tables(url) >= {"ir_hard_stretches"}
