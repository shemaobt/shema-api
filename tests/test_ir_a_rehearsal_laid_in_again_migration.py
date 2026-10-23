"""ENG-1407 — joined takes may share their bytes across passes; hand-recorded ones still may not.

Same constraint as the sibling migration tests: Alembic's full chain does not run on SQLite,
so the schema is built from ``Base.metadata``, stamped at this revision and walked down, and the
rows are written in the shape the previous revision stored them.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

import app.db.models  # noqa: F401  (populates Base.metadata with every table)
from app.core.database import Base
from tests.alembic_harness import indexes_of, run_alembic, scalar, unique_constraints_of

pytestmark = pytest.mark.migration

REVISION = "20261022_swap01"
PREVIOUS_REVISION = "20261022_grain01"

SESSION = "a0000000-0000-0000-0000-000000000001"
REHEARSAL = "c0000000-0000-0000-0000-000000000001"
KEY = "takes/a/ensaio/aaaa/tomada.m4a"


async def _insert_take(
    url: str, take_id: str, *, pass_number: int, origin: str | None, sha256: str = "a" * 64
) -> None:
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO ir_takes (id, session_id, device_id, pericope, kind, scope,"
                " ordinal, pass_number, storage_key, size_bytes, sha256, crc32c, content_type,"
                " origin, created_at, recorded_at)"
                " VALUES (:id, :session, 'tablet-1', 'P03', 'ensaio', 'parte-2', 2, :pass, :key,"
                " 2048, :sha, 'AAAAAAA=', 'audio/mp4', :origin, '2026-10-22 08:00:00',"
                " '2026-10-22 08:00:00')"
            ),
            {
                "id": take_id,
                "session": SESSION,
                "pass": pass_number,
                "key": KEY,
                "sha": sha256,
                "origin": origin,
            },
        )
    await engine.dispose()


@pytest.fixture()
async def before_the_migration(tmp_path) -> str:
    url = f"sqlite+aiosqlite:///{tmp_path / 'ir_a_rehearsal_laid_in_again_migration.db'}"
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    stamped = run_alembic(url, "stamp", REVISION)
    assert stamped.returncode == 0, stamped.stderr
    down = run_alembic(url, "downgrade", PREVIOUS_REVISION)
    assert down.returncode == 0, down.stderr
    return url


async def test_two_joined_takes_of_the_same_bytes_at_two_passes_are_both_kept(
    before_the_migration,
) -> None:
    url = before_the_migration
    up = run_alembic(url, "upgrade", REVISION)
    assert up.returncode == 0, up.stderr

    await _insert_take(url, "b0000000-0000-0000-0000-000000000001", pass_number=1, origin=REHEARSAL)
    await _insert_take(url, "b0000000-0000-0000-0000-000000000003", pass_number=3, origin=REHEARSAL)

    assert (
        await scalar(url, "SELECT count(*) FROM ir_takes WHERE storage_key = :k", {"k": KEY}) == 2
    )


async def test_two_hand_recorded_takes_of_the_same_bytes_are_still_refused(
    before_the_migration,
) -> None:
    url = before_the_migration
    up = run_alembic(url, "upgrade", REVISION)
    assert up.returncode == 0, up.stderr
    await _insert_take(url, "b0000000-0000-0000-0000-000000000001", pass_number=1, origin=None)

    with pytest.raises(IntegrityError):
        await _insert_take(url, "b0000000-0000-0000-0000-000000000002", pass_number=2, origin=None)


async def test_the_migration_walks_down_where_no_bytes_are_shared(before_the_migration) -> None:
    url = before_the_migration
    up = run_alembic(url, "upgrade", REVISION)
    assert up.returncode == 0, up.stderr
    await _insert_take(url, "b0000000-0000-0000-0000-000000000001", pass_number=1, origin=REHEARSAL)

    down = run_alembic(url, "downgrade", PREVIOUS_REVISION)

    assert down.returncode == 0, down.stderr
    indexes = await indexes_of(url, "ir_takes")
    assert indexes["uq_ir_takes_session_kind_sha256"] == (True, ["session_id", "kind", "sha256"])
    assert "uq_ir_takes_session_joined_pass" not in indexes
    assert (await unique_constraints_of(url, "ir_takes"))["uq_ir_takes_session_storage_key"] == [
        "session_id",
        "storage_key",
    ]
