"""ENG-1305 — a forced release records the blockers it passed.

Same constraint as the sibling migration tests: Alembic's full chain does not run on SQLite,
so the schema is built from ``Base.metadata``, stamped at this revision and walked down, and the
row is written in the shape the previous revision stored it.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

import app.db.models  # noqa: F401  (populates Base.metadata with every table)
from app.core.database import Base
from tests.alembic_harness import columns_of, run_alembic, scalar

pytestmark = pytest.mark.migration

REVISION = "20261021_forced01"
PREVIOUS_REVISION = "20261021_stale01"

RELEASE = "e0000000-0000-0000-0000-000000000001"


async def _insert_forced_release(url: str) -> None:
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO ir_releases (id, session_id, project_id, pericope, version,"
                " package_sha256, packet, approved_at, forced_by, forced_at)"
                " VALUES (:id, 'sessao-1', 'equipe-1', 'P03', 1, :sha, '{}',"
                " '2026-10-01 08:00:00', 'facilitadora-1', '2026-10-01 08:00:00')"
            ),
            {"id": RELEASE, "sha": "a" * 64},
        )
    await engine.dispose()


@pytest.fixture()
async def before_the_migration(tmp_path) -> str:
    url = f"sqlite+aiosqlite:///{tmp_path / 'ir_forced_blockers_migration.db'}"
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    stamped = run_alembic(url, "stamp", REVISION)
    assert stamped.returncode == 0, stamped.stderr
    down = run_alembic(url, "downgrade", PREVIOUS_REVISION)
    assert down.returncode == 0, down.stderr
    await _insert_forced_release(url)
    return url


async def test_a_release_forced_before_the_migration_names_no_blockers(before_the_migration):
    url = before_the_migration

    up = run_alembic(url, "upgrade", REVISION)

    assert up.returncode == 0, up.stderr
    assert "forced_blockers" in await columns_of(url, "ir_releases")
    assert (
        await scalar(url, "SELECT forced_blockers FROM ir_releases WHERE id = :id", {"id": RELEASE})
        is None
    )


async def test_the_migration_walks_down(before_the_migration) -> None:
    url = before_the_migration
    up = run_alembic(url, "upgrade", REVISION)
    assert up.returncode == 0, up.stderr

    down = run_alembic(url, "downgrade", PREVIOUS_REVISION)

    assert down.returncode == 0, down.stderr
    assert "forced_blockers" not in await columns_of(url, "ir_releases")
    assert await scalar(url, "SELECT count(*) FROM ir_releases", {}) == 1
