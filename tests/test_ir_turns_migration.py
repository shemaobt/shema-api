"""ENG-626's migration: the table a resent turn is answered from instead of repeating.

Walked down and back up rather than only inspected, because a migration that creates the shape
and cannot undo it is a migration nobody can deploy behind.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

import app.db.models  # noqa: F401  (populates Base.metadata with every table)
from app.core.database import Base
from tests.alembic_harness import columns_of, run_alembic, tables_of, unique_constraints_of

pytestmark = pytest.mark.migration

REVISION = "20260916_turn01"
PREVIOUS_REVISION = "20260911_rel02"


@pytest.fixture()
async def ir_turns_database(tmp_path) -> str:
    """The post-migration schema, stamped as applied, ready to walk down and back up.

    Alembic's full chain does not run on SQLite, so the shape is the neighbours': build from
    `Base.metadata`, which is the post-migration schema, and stamp it as applied.
    """
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'ir_turns.db'}"
    engine = create_async_engine(database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()

    stamped = run_alembic(database_url, "stamp", REVISION)
    assert stamped.returncode == 0, stamped.stderr
    return database_url


async def _assert_the_table_is_whole(url: str) -> None:
    assert await tables_of(url) >= {"ir_turns"}
    assert await columns_of(url, "ir_turns") == {
        "id",
        "session_id",
        "turn_id",
        "response",
        "created_at",
    }
    unique = await unique_constraints_of(url, "ir_turns")
    assert unique["uq_ir_turns_session_turn"] == ["session_id", "turn_id"]


async def test_the_migration_adds_the_turns_table_with_its_unique_pair(
    ir_turns_database: str,
) -> None:
    """Checked again after the round trip, not only on the stamped state.

    The fixture builds its starting schema from ``Base.metadata``, which is the model, not
    this migration — so a shape asserted only there would pass whether or not `upgrade()`
    actually recreates it. What proves the migration is the shape coming back after
    `downgrade()` has torn it down.
    """
    url = ir_turns_database

    await _assert_the_table_is_whole(url)

    down = run_alembic(url, "downgrade", PREVIOUS_REVISION)
    assert down.returncode == 0, down.stderr
    assert "ir_turns" not in await tables_of(url)

    up = run_alembic(url, "upgrade", REVISION)
    assert up.returncode == 0, up.stderr
    await _assert_the_table_is_whole(url)
