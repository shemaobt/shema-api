"""ENG-1739 — a stretch says whether it was retired because its part was recorded again.

Same constraint as the sibling migration tests: Alembic's full chain does not run on SQLite,
so the schema is built from ``Base.metadata``, stamped at this revision and walked down, and the
rows are written in the shape the previous revision stored them.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

import app.db.models  # noqa: F401  (populates Base.metadata with every table)
from app.core.database import Base
from tests.alembic_harness import columns_of, run_alembic, scalar

pytestmark = pytest.mark.migration

REVISION = "20261021_stale01"
PREVIOUS_REVISION = "20261019_takerec01"

SESSION = "a0000000-0000-0000-0000-000000000001"
RETIRED = "d0000000-0000-0000-0000-000000000001"
STANDING = "d0000000-0000-0000-0000-000000000002"
STORED_AT = "2026-10-01 08:00:00"


async def _insert_segment(url: str, segment_id: str, superseded_at: str | None) -> None:
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO ir_segments (id, session_id, ordinal, take_id, starts_ms, ends_ms,"
                " pass_number, tellings, transcript, superseded_at, created_at)"
                " VALUES (:id, :session, :ordinal, 'ensaio-1', 0, 9000, 1, 1,"
                " 'o que a equipe contou', :superseded_at, :stored)"
            ),
            {
                "id": segment_id,
                "session": SESSION,
                "ordinal": 1 if superseded_at else 2,
                "superseded_at": superseded_at,
                "stored": STORED_AT,
            },
        )
    await engine.dispose()


@pytest.fixture()
async def before_the_migration(tmp_path) -> str:
    url = f"sqlite+aiosqlite:///{tmp_path / 'ir_stale_stretch_migration.db'}"
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    stamped = run_alembic(url, "stamp", REVISION)
    assert stamped.returncode == 0, stamped.stderr
    down = run_alembic(url, "downgrade", PREVIOUS_REVISION)
    assert down.returncode == 0, down.stderr
    await _insert_segment(url, RETIRED, STORED_AT)
    await _insert_segment(url, STANDING, None)
    return url


async def test_a_stretch_retired_before_is_not_served_as_one_waiting_to_be_told_again(
    before_the_migration,
) -> None:
    url = before_the_migration

    up = run_alembic(url, "upgrade", REVISION)

    assert up.returncode == 0, up.stderr
    for segment in (RETIRED, STANDING):
        assert not await scalar(
            url, "SELECT stale FROM ir_segments WHERE id = :id", {"id": segment}
        ), "uma linha guardada antes não podia nascer marcada como regravada"


async def test_the_migration_walks_down(before_the_migration) -> None:
    url = before_the_migration
    up = run_alembic(url, "upgrade", REVISION)
    assert up.returncode == 0, up.stderr

    down = run_alembic(url, "downgrade", PREVIOUS_REVISION)

    assert down.returncode == 0, down.stderr
    assert "stale" not in await columns_of(url, "ir_segments")
    assert (
        await scalar(
            url, "SELECT count(*) FROM ir_segments WHERE session_id = :id", {"id": SESSION}
        )
        == 2
    )
