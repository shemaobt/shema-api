from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

import app.db.models  # noqa: F401  (populates Base.metadata with every table)
from app.core.database import Base
from tests.alembic_harness import run_alembic, tables_of

pytestmark = pytest.mark.migration

REVISION = "20260930_idem01"
PREVIOUS_REVISION = "20260929_warn01"
TABLE = "ir_idempotency_keys"


@pytest.fixture()
async def idempotency_database(tmp_path) -> str:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'ir_idempotency_keys.db'}"
    engine = create_async_engine(database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()

    stamped = run_alembic(database_url, "stamp", REVISION)
    assert stamped.returncode == 0, stamped.stderr
    return database_url


async def test_the_downgrade_drops_the_idempotency_table_and_the_upgrade_creates_it(
    idempotency_database: str,
) -> None:
    url = idempotency_database

    down = run_alembic(url, "downgrade", PREVIOUS_REVISION)
    assert down.returncode == 0, down.stderr
    assert TABLE not in await tables_of(url)

    up = run_alembic(url, "upgrade", REVISION)
    assert up.returncode == 0, up.stderr
    assert TABLE in await tables_of(url)
