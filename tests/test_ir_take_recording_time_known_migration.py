"""ENG-1760 — a take says whether its recording time is its own.

Same constraint as the sibling migration tests: Alembic's full chain does not run on SQLite,
so the schema is built from ``Base.metadata``, stamped at this revision and walked down, and the
rows are written in the shape the previous revision stored them.
"""

import json

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

import app.db.models  # noqa: F401  (populates Base.metadata with every table)
from app.core.database import Base
from tests.alembic_harness import columns_of, run_alembic, scalar

pytestmark = pytest.mark.migration

REVISION = "20261022_known01"
PREVIOUS_REVISION = "20261021_opfor01"

SESSION = "a0000000-0000-0000-0000-000000000001"
OTHER_SESSION = "a0000000-0000-0000-0000-000000000002"
ARRIVED_ONLY = "b0000000-0000-0000-0000-000000000001"
TABLET_TIMED = "b0000000-0000-0000-0000-000000000002"
JOINED = "b0000000-0000-0000-0000-000000000003"
SPLICED = "b0000000-0000-0000-0000-000000000004"
NOT_NAMED = "b0000000-0000-0000-0000-000000000005"
UPLOADED = "2026-10-01 08:00:00"
RECORDED_ON_THE_TABLET = "2026-10-01 07:42:00"


async def _insert_session(url: str, session_id: str, back_translation: dict) -> None:
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO ir_sessions (id, pericope, language, status, messages,"
                " after_panorama, coverage_state, back_translation, created_at, updated_at)"
                " VALUES (:id, 'P03', 'pt', 'active', '[]', 0, '{}', :told, :uploaded,"
                " :uploaded)"
            ),
            {"id": session_id, "told": json.dumps(back_translation), "uploaded": UPLOADED},
        )
    await engine.dispose()


async def _insert_take(
    url: str,
    take_id: str,
    *,
    session_id: str = SESSION,
    recorded_at: str = UPLOADED,
    origin: str | None = None,
) -> None:
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO ir_takes (id, session_id, device_id, pericope, kind, scope,"
                " ordinal, storage_key, size_bytes, sha256, crc32c, content_type, created_at,"
                " recorded_at, origin) VALUES (:id, :session, 'tablet-1', 'P03', 'ensaio',"
                " 'parte-1', 1, :key, 2048, :sha, 'AAAAAAA=', 'audio/wav', :uploaded,"
                " :recorded_at, :origin)"
            ),
            {
                "id": take_id,
                "session": session_id,
                "key": f"takes/{take_id}.wav",
                "sha": take_id.replace("-", "")[-32:] * 2,
                "uploaded": UPLOADED,
                "recorded_at": recorded_at,
                "origin": origin,
            },
        )
    await engine.dispose()


def a_laid_in_sentence(take_id: str) -> dict:
    return {
        "sentence_id": "sentence-0001",
        "segment_id": "s0000000-0000-0000-0000-000000000001",
        "previous_take_id": ARRIVED_ONLY,
        "take_id": take_id,
        "starts_ms": 0,
        "ends_ms": 1000,
        "sha256": "d" * 64,
        "storage_key": f"takes/{take_id}.wav",
        "heard_before": False,
    }


@pytest.fixture()
async def before_the_migration(tmp_path) -> str:
    url = f"sqlite+aiosqlite:///{tmp_path / 'ir_take_recording_time_known_migration.db'}"
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    stamped = run_alembic(url, "stamp", REVISION)
    assert stamped.returncode == 0, stamped.stderr
    down = run_alembic(url, "downgrade", PREVIOUS_REVISION)
    assert down.returncode == 0, down.stderr
    return url


async def known(url: str, take_id: str) -> bool:
    return bool(
        await scalar(url, "SELECT recorded_at_known FROM ir_takes WHERE id = :id", {"id": take_id})
    )


async def test_a_take_stored_with_only_its_arrival_has_no_recording_time_of_its_own(
    before_the_migration,
) -> None:
    url = before_the_migration
    await _insert_take(url, ARRIVED_ONLY)

    up = run_alembic(url, "upgrade", REVISION)

    assert up.returncode == 0, up.stderr
    assert await known(url, ARRIVED_ONLY) is False


async def test_a_take_the_tablet_timed_has_its_recording_time_after_the_migration(
    before_the_migration,
) -> None:
    url = before_the_migration
    await _insert_take(url, TABLET_TIMED, recorded_at=RECORDED_ON_THE_TABLET)

    up = run_alembic(url, "upgrade", REVISION)

    assert up.returncode == 0, up.stderr
    assert await known(url, TABLET_TIMED) is True


async def test_a_joined_part_has_its_recording_time_after_the_migration(
    before_the_migration,
) -> None:
    url = before_the_migration
    await _insert_take(url, JOINED, origin="c0000000-0000-0000-0000-000000000001")

    up = run_alembic(url, "upgrade", REVISION)

    assert up.returncode == 0, up.stderr
    assert await known(url, JOINED) is True


async def test_a_spliced_part_named_by_a_laid_in_sentence_has_its_recording_time(
    before_the_migration,
) -> None:
    url = before_the_migration
    await _insert_session(url, SESSION, {"sentences": [a_laid_in_sentence(SPLICED)]})
    await _insert_session(url, OTHER_SESSION, {"sentences": []})
    await _insert_take(url, SPLICED)
    await _insert_take(url, NOT_NAMED, session_id=OTHER_SESSION)

    up = run_alembic(url, "upgrade", REVISION)

    assert up.returncode == 0, up.stderr
    assert await known(url, SPLICED) is True
    assert await known(url, NOT_NAMED) is False


async def test_the_migration_walks_back_down_and_up_again(before_the_migration) -> None:
    url = before_the_migration
    up = run_alembic(url, "upgrade", REVISION)
    assert up.returncode == 0, up.stderr

    down = run_alembic(url, "downgrade", PREVIOUS_REVISION)

    assert down.returncode == 0, down.stderr
    assert "recorded_at_known" not in await columns_of(url, "ir_takes")
    again = run_alembic(url, "upgrade", REVISION)
    assert again.returncode == 0, again.stderr
    assert "recorded_at_known" in await columns_of(url, "ir_takes")
