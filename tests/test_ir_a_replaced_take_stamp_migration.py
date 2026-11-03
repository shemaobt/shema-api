"""ENG-1256 — a take keeps the time it stopped being live, and a stored take has none.

Same constraint as the sibling migration tests: Alembic's full chain does not run on SQLite,
so the schema is built from ``Base.metadata``, stamped at the head and walked down to the
revision before this one, and a take is written in the shape that revision stored it.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

import app.db.models  # noqa: F401  (populates Base.metadata with every table)
from app.core.database import Base
from tests.alembic_harness import columns_of, run_alembic, scalar

pytestmark = pytest.mark.migration

REVISION = "20261029_stamp01"
PREVIOUS_REVISION = "20261028_check01"

TAKE = "b0000000-0000-0000-0000-000000000001"
SESSION = "a0000000-0000-0000-0000-000000000001"


async def _stored(url: str) -> None:
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO ir_takes (id, session_id, device_id, pericope, kind, scope,"
                " ordinal, storage_key, size_bytes, sha256, crc32c, content_type, created_at)"
                " VALUES (:id, :session, 'tablet-1', 'P03', 'ensaio', 'parte-1', 1,"
                " 'takes/a0000000/ensaio/aaaa', 2048, :sha, 'AAAAAAA=', 'audio/wav',"
                " '2026-10-01 08:00:00')"
            ),
            {"id": TAKE, "session": SESSION, "sha": "a" * 64},
        )
    await engine.dispose()


@pytest.fixture()
async def before_the_migration(tmp_path) -> str:
    url = f"sqlite+aiosqlite:///{tmp_path / 'ir_replaced_take_stamp_migration.db'}"
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    stamped = run_alembic(url, "stamp", "head")
    assert stamped.returncode == 0, stamped.stderr
    down = run_alembic(url, "downgrade", PREVIOUS_REVISION)
    assert down.returncode == 0, down.stderr
    await _stored(url)
    return url


async def test_the_stamp_column_is_added_and_a_stored_take_is_given_no_time(
    before_the_migration,
) -> None:
    url = before_the_migration
    assert "superseded_at" not in await columns_of(url, "ir_takes")

    up = run_alembic(url, "upgrade", REVISION)

    assert up.returncode == 0, up.stderr
    assert "superseded_at" in await columns_of(url, "ir_takes")
    assert await scalar(url, "SELECT sha256 FROM ir_takes WHERE id = :id", {"id": TAKE}) == "a" * 64
    assert (
        await scalar(url, "SELECT superseded_at FROM ir_takes WHERE id = :id", {"id": TAKE}) is None
    ), "uma tomada guardada antes ganhou uma hora que ninguém registrou"

    down = run_alembic(url, "downgrade", PREVIOUS_REVISION)

    assert down.returncode == 0, down.stderr
    assert "superseded_at" not in await columns_of(url, "ir_takes")
    assert await scalar(url, "SELECT sha256 FROM ir_takes WHERE id = :id", {"id": TAKE}) == "a" * 64
