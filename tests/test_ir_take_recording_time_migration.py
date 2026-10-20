"""ENG-1273 — a take keeps its recording time and length, and one session holds its bytes once.

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
from tests.alembic_harness import columns_of, indexes_of, run_alembic, scalar

pytestmark = pytest.mark.migration

REVISION = "20261019_takerec01"
PREVIOUS_REVISION = "20261019_join01"

TAKE = "b0000000-0000-0000-0000-000000000001"
SCENE = "c0000000-0000-0000-0000-000000000001"
SESSION = "a0000000-0000-0000-0000-000000000001"
UPLOADED = "2026-10-01 08:00:00"
NEW_COLUMNS = {"recorded_at", "duration_ms", "device_clock_offset_ms"}
INDEX = "uq_ir_takes_session_kind_sha256"


async def _insert_take(url: str, take_id: str, key: str, sha256: str) -> None:
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO ir_takes (id, session_id, device_id, pericope, kind, scope,"
                " ordinal, storage_key, size_bytes, sha256, crc32c, content_type, created_at)"
                " VALUES (:id, :session, 'tablet-1', 'P03', 'ensaio', 'parte-1', 1, :key,"
                " 2048, :sha, 'AAAAAAA=', 'audio/wav', :uploaded)"
            ),
            {"id": take_id, "session": SESSION, "key": key, "sha": sha256, "uploaded": UPLOADED},
        )
    await engine.dispose()


async def _insert_scene_rehearsal(url: str) -> None:
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO ir_scene_rehearsals (id, session_id, pericope, n, device_id,"
                " storage_key, size_bytes, sha256, crc32c, content_type, created_at)"
                " VALUES (:id, :session, 'P03', 1, 'tablet-1', 'cenas/1', 2048, :sha,"
                " 'AAAAAAA=', 'audio/wav', :uploaded)"
            ),
            {"id": SCENE, "session": SESSION, "sha": "c" * 64, "uploaded": UPLOADED},
        )
    await engine.dispose()


@pytest.fixture()
async def before_the_migration(tmp_path) -> str:
    url = f"sqlite+aiosqlite:///{tmp_path / 'ir_take_recording_time_migration.db'}"
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    stamped = run_alembic(url, "stamp", REVISION)
    assert stamped.returncode == 0, stamped.stderr
    down = run_alembic(url, "downgrade", PREVIOUS_REVISION)
    assert down.returncode == 0, down.stderr
    await _insert_take(url, TAKE, "takes/a/ensaio/aaaa/tomada.wav", "a" * 64)
    await _insert_scene_rehearsal(url)
    return url


async def test_a_take_stored_before_keeps_its_upload_time_as_its_recording_time_and_no_length(
    before_the_migration,
) -> None:
    url = before_the_migration

    up = run_alembic(url, "upgrade", REVISION)

    assert up.returncode == 0, up.stderr
    row = {"id": TAKE}
    assert await scalar(url, "SELECT recorded_at FROM ir_takes WHERE id = :id", row) == UPLOADED
    assert await scalar(url, "SELECT duration_ms FROM ir_takes WHERE id = :id", row) is None
    assert (
        await scalar(url, "SELECT device_clock_offset_ms FROM ir_takes WHERE id = :id", row) is None
    )


async def test_a_scene_rehearsal_stored_before_keeps_its_upload_time_as_its_recording_time(
    before_the_migration,
) -> None:
    url = before_the_migration

    up = run_alembic(url, "upgrade", REVISION)

    assert up.returncode == 0, up.stderr
    assert (
        await scalar(
            url, "SELECT recorded_at FROM ir_scene_rehearsals WHERE id = :id", {"id": SCENE}
        )
        == UPLOADED
    )


async def test_a_second_row_of_the_same_bytes_is_refused_and_declared_parts_are_not(
    before_the_migration,
) -> None:
    url = before_the_migration
    up = run_alembic(url, "upgrade", REVISION)
    assert up.returncode == 0, up.stderr

    with pytest.raises(IntegrityError):
        await _insert_take(
            url, "b0000000-0000-0000-0000-000000000002", "takes/a/ensaio/aaaa/tomada.m4a", "a" * 64
        )
    await _insert_take(url, "b0000000-0000-0000-0000-000000000003", "declarada-1", "")
    await _insert_take(url, "b0000000-0000-0000-0000-000000000004", "declarada-2", "")

    assert await scalar(url, "SELECT count(*) FROM ir_takes WHERE sha256 = ''", {}) == 2


async def test_the_migration_walks_down(before_the_migration) -> None:
    url = before_the_migration
    up = run_alembic(url, "upgrade", REVISION)
    assert up.returncode == 0, up.stderr

    down = run_alembic(url, "downgrade", PREVIOUS_REVISION)

    assert down.returncode == 0, down.stderr
    assert not NEW_COLUMNS & await columns_of(url, "ir_takes")
    assert "recorded_at" not in await columns_of(url, "ir_scene_rehearsals")
    assert INDEX not in await indexes_of(url, "ir_takes")
    assert (
        await scalar(url, "SELECT created_at FROM ir_takes WHERE id = :id", {"id": TAKE})
        == UPLOADED
    )
