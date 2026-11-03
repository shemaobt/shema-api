"""ENG-1207 — a take keeps the scene rehearsal it was joined from.

Same constraint as the sibling migration tests: Alembic's full chain does not run on SQLite,
so the schema is built from ``Base.metadata``, stamped at the head and walked down through every
later revision, whose indexes read the column this one adds, and a take is written in the shape
the previous revision stored it.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

import app.db.models  # noqa: F401  (populates Base.metadata with every table)
from app.core.database import Base
from tests.alembic_harness import columns_of, run_alembic, scalar

pytestmark = pytest.mark.migration

REVISION = "20261019_join01"
PREVIOUS_REVISION = "20261019_retel01"

TAKE = "b0000000-0000-0000-0000-000000000001"
STORED = (
    "SELECT session_id, kind, scope, ordinal, storage_key, content_type"
    " FROM ir_takes WHERE id = :id"
)
AS_STORED = (
    "a0000000-0000-0000-0000-000000000001",
    "ensaio",
    "parte-1",
    1,
    "takes/a0000000/ensaio/aaaa",
    "audio/wav",
)


async def _row(url: str) -> tuple:
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        row = (await conn.execute(text(STORED), {"id": TAKE})).one()
    await engine.dispose()
    return tuple(row)


async def _stored(url: str) -> None:
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO ir_takes (id, session_id, device_id, pericope, kind, scope,"
                " ordinal, storage_key, size_bytes, sha256, crc32c, content_type, created_at)"
                " VALUES (:id, :session, 'tablet-1', 'P03', :kind, :scope, :ordinal, :key,"
                " 2048, :sha, 'AAAAAAA=', :content_type, '2026-10-01 08:00:00')"
            ),
            dict(
                zip(
                    ("session", "kind", "scope", "ordinal", "key", "content_type"),
                    AS_STORED,
                    strict=True,
                ),
                id=TAKE,
                sha="a" * 64,
            ),
        )
    await engine.dispose()


@pytest.fixture()
async def before_the_migration(tmp_path) -> str:
    url = f"sqlite+aiosqlite:///{tmp_path / 'ir_take_origin_migration.db'}"
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


async def test_the_origin_column_is_added_and_a_stored_take_keeps_everything_it_had(
    before_the_migration,
) -> None:
    url = before_the_migration
    assert "origin" not in await columns_of(url, "ir_takes")

    up = run_alembic(url, "upgrade", REVISION)

    assert up.returncode == 0, up.stderr
    assert "origin" in await columns_of(url, "ir_takes")
    assert await _row(url) == AS_STORED
    assert await scalar(url, "SELECT origin FROM ir_takes WHERE id = :id", {"id": TAKE}) is None, (
        "uma tomada guardada antes não veio de junção nenhuma e ganhou uma origem"
    )

    down = run_alembic(url, "downgrade", PREVIOUS_REVISION)

    assert down.returncode == 0, down.stderr
    assert "origin" not in await columns_of(url, "ir_takes")
    assert await _row(url) == AS_STORED
