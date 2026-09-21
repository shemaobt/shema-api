"""ENG-735: a production dump can hold an exact (project_id, title) duplicate that
`20260601_0001`'s unique index was never proven against.

Same constraint as the sibling migration tests: Alembic's full chain does not run on
SQLite, so this builds the schema from ``Base.metadata`` — the post-migration shape,
partial unique index included — then drops just that index to recreate the moment
before `20260601_0001` ran. That is the only way to get duplicate titles into the
table at all: with the index standing, the insert below would raise the same
`IntegrityError` the index exists to raise.

Walking `upgrade` from `PREVIOUS_REVISION` to `TARGET_REVISION` runs both
`20260916_0001` (the dedupe) and `20260601_0001` (the index) in the order they will
run against a real restore. A dump this reproduces the bug against fails at
`20260601_0001` with a `UniqueViolationError`; the fix makes the same walk succeed.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

import app.db.models  # noqa: F401  (populates Base.metadata with every table)
from app.core.database import Base
from tests.alembic_harness import run_alembic, scalar

pytestmark = pytest.mark.migration

PREVIOUS_REVISION = "20260724_0002"
TARGET_REVISION = "20260601_0001"

_INDEX_NAME = "uq_oc_recordings_project_title"

_INSERT_RECORDING = """
    INSERT INTO oc_recordings (
        id, project_id, genre_id, subcategory_id, title, duration_seconds,
        file_size_bytes, format, upload_status, cleaning_status, splitting_status,
        split_from_id, review_flags, recorded_at, created_at, updated_at
    ) VALUES (
        :id, :project_id, 'genre', 'subcat', :title, 1.0,
        1, 'wav', 'local', 'none', :splitting_status,
        :split_from_id, '[]', :now, :created_at, :now
    )
"""


async def _seed(database_url: str) -> dict[str, str]:
    engine = create_async_engine(database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text(f"DROP INDEX {_INDEX_NAME}"))

    project_id = str(uuid.uuid4())
    older_id = str(uuid.uuid4())
    newer_id = str(uuid.uuid4())
    exempt_id = str(uuid.uuid4())
    archived_id = str(uuid.uuid4())

    async with engine.begin() as conn:
        for row_id, created_at, splitting_status, split_from_id in (
            (older_id, "2026-01-01 00:00:00", "none", None),
            (newer_id, "2026-01-02 00:00:00", "none", None),
            # Exempt: split-derived, so it may keep the same title as the others.
            (exempt_id, "2026-01-03 00:00:00", "none", older_id),
            # Exempt: an archived split parent, the other half of the index's WHERE.
            (archived_id, "2026-01-04 00:00:00", "archived_after_split", None),
        ):
            await conn.execute(
                text(_INSERT_RECORDING),
                {
                    "id": row_id,
                    "project_id": project_id,
                    "title": "História24_Alcino",
                    "splitting_status": splitting_status,
                    "split_from_id": split_from_id,
                    "now": "2026-01-04 00:00:00",
                    "created_at": created_at,
                },
            )
    await engine.dispose()
    return {
        "project_id": project_id,
        "older_id": older_id,
        "newer_id": newer_id,
        "exempt_id": exempt_id,
        "archived_id": archived_id,
    }


@pytest.fixture()
async def duplicate_database(tmp_path) -> dict[str, str]:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'oc_recordings_dedupe.db'}"
    seeded = await _seed(database_url)

    stamped = run_alembic(database_url, "stamp", PREVIOUS_REVISION)
    assert stamped.returncode == 0, stamped.stderr

    return {"url": database_url, **seeded}


async def test_upgrade_past_the_duplicate_reaches_the_unique_index(duplicate_database):
    url = duplicate_database["url"]

    up = run_alembic(url, "upgrade", TARGET_REVISION)
    assert up.returncode == 0, up.stderr


async def test_the_earliest_row_keeps_its_title_and_the_later_one_is_renamed(duplicate_database):
    url = duplicate_database["url"]
    older_id = duplicate_database["older_id"]
    newer_id = duplicate_database["newer_id"]

    assert run_alembic(url, "upgrade", TARGET_REVISION).returncode == 0

    assert (
        await scalar(url, "SELECT title FROM oc_recordings WHERE id = :id", {"id": older_id})
        == "História24_Alcino"
    )
    assert (
        await scalar(url, "SELECT title FROM oc_recordings WHERE id = :id", {"id": newer_id})
        == f"História24_Alcino (dup {newer_id})"
    )


async def test_the_exempt_split_derived_row_keeps_its_original_title(duplicate_database):
    url = duplicate_database["url"]
    exempt_id = duplicate_database["exempt_id"]

    assert run_alembic(url, "upgrade", TARGET_REVISION).returncode == 0

    assert (
        await scalar(url, "SELECT title FROM oc_recordings WHERE id = :id", {"id": exempt_id})
        == "História24_Alcino"
    )


async def test_the_archived_split_parent_keeps_its_original_title(duplicate_database):
    url = duplicate_database["url"]
    archived_id = duplicate_database["archived_id"]

    assert run_alembic(url, "upgrade", TARGET_REVISION).returncode == 0

    assert (
        await scalar(url, "SELECT title FROM oc_recordings WHERE id = :id", {"id": archived_id})
        == "História24_Alcino"
    )


async def test_no_row_is_lost_by_the_dedupe(duplicate_database):
    url = duplicate_database["url"]

    assert run_alembic(url, "upgrade", TARGET_REVISION).returncode == 0

    assert await scalar(url, "SELECT count(*) FROM oc_recordings", {}) == 4
