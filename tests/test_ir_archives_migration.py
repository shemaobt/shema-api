"""ENG-1261 — Zerar's archive: one table, and a nullable stamp on five tables of work.

Same constraint as the sibling migration tests: Alembic's full chain does not run on SQLite,
so the schema is built from ``Base.metadata``, stamped at this revision and walked down, and
one row of each stamped table is written in the shape the previous revision stored it.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

import app.db.models  # noqa: F401  (populates Base.metadata with every table)
from app.core.database import Base
from tests.alembic_harness import columns_of, run_alembic, scalar, tables_of

pytestmark = pytest.mark.migration

REVISION = "20261006_zera01"
PREVIOUS_REVISION = "20261002_earl01"

SESSION = "a0000000-0000-0000-0000-000000000001"
STAMPED = ("ir_sessions", "ir_takes", "ir_segments", "ir_coverage_events", "ir_releases")

AS_STORED = {
    "ir_sessions": (
        "INSERT INTO ir_sessions (id, project_id, pericope, language, status, messages,"
        " after_panorama, coverage_state, kept_takes, back_translation, created_at, updated_at)"
        " VALUES (:session, 'team-1', 'P03', 'pt', 'in_progress', '[]', 0, '{}', '{}', '{}',"
        " '2026-10-01 08:00:00', '2026-10-01 08:00:00')"
    ),
    "ir_takes": (
        "INSERT INTO ir_takes (id, session_id, device_id, project_id, pericope, kind, scope,"
        " storage_key, size_bytes, sha256, crc32c, content_type, created_at) VALUES"
        " ('take-1', :session, 'tablet-1', 'team-1', 'P03', 'ensaio', 'passagem-inteira',"
        " 'takes/x', 2048, 'aa', 'AAAAAAA=', 'audio/mp4', '2026-10-01 08:00:00')"
    ),
    "ir_segments": (
        "INSERT INTO ir_segments (id, session_id, project_id, ordinal, take_id, starts_ms,"
        " ends_ms, pass_number, tellings, created_at) VALUES ('segment-1', :session, 'team-1',"
        " 1, 'take-1', 0, 61000, 1, 1, '2026-10-01 08:00:00')"
    ),
    "ir_coverage_events": (
        "INSERT INTO ir_coverage_events (id, session_id, project_id, pericope, element_key,"
        " status, at) VALUES ('event-1', :session, 'team-1', 'P03', 'being:B3', 'engaged',"
        " '2026-10-01 08:00:00')"
    ),
    "ir_releases": (
        "INSERT INTO ir_releases (id, session_id, project_id, pericope, version,"
        " package_sha256, packet, approved_at) VALUES ('release-1', :session, 'team-1', 'P03',"
        " 1, 'bb', '{}', '2026-10-01 08:00:00')"
    ),
}


async def _rows(url: str) -> dict[str, list[tuple]]:
    engine = create_async_engine(url)
    read: dict[str, list[tuple]] = {}
    async with engine.connect() as conn:
        for table in STAMPED:
            columns = sorted((await columns_of(url, table)) - {"archive_id"})
            listed = ", ".join(columns)
            rows = await conn.execute(text(f"SELECT {listed} FROM {table} ORDER BY id"))
            read[table] = [tuple(row) for row in rows.all()]
    await engine.dispose()
    return read


async def _stored(url: str) -> None:
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        for insert in AS_STORED.values():
            await conn.execute(text(insert), {"session": SESSION})
    await engine.dispose()


@pytest.fixture()
async def before_the_migration(tmp_path) -> str:
    url = f"sqlite+aiosqlite:///{tmp_path / 'ir_archives_migration.db'}"
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    stamped = run_alembic(url, "stamp", REVISION)
    assert stamped.returncode == 0, stamped.stderr
    down = run_alembic(url, "downgrade", PREVIOUS_REVISION)
    assert down.returncode == 0, down.stderr
    await _stored(url)
    return url


async def test_the_archive_migration_adds_the_table_and_the_five_columns_and_walks_back(
    before_the_migration,
) -> None:
    url = before_the_migration
    assert "ir_archives" not in await tables_of(url)
    stored = await _rows(url)
    assert all(stored[table] for table in STAMPED)

    up = run_alembic(url, "upgrade", REVISION)

    assert up.returncode == 0, up.stderr
    assert {"id", "project_id", "pericope", "archived_at", "archived_by", "snapshot"} <= (
        await columns_of(url, "ir_archives")
    )
    for table in STAMPED:
        assert "archive_id" in await columns_of(url, table), table
        assert await scalar(url, f"SELECT count(*) FROM {table} WHERE archive_id IS NULL", {}) == 1
    assert await _rows(url) == stored

    down = run_alembic(url, "downgrade", PREVIOUS_REVISION)

    assert down.returncode == 0, down.stderr
    assert "ir_archives" not in await tables_of(url)
    for table in STAMPED:
        assert "archive_id" not in await columns_of(url, table), table
    assert await _rows(url) == stored
