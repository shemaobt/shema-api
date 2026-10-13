"""ENG-1312 — the scene rehearsal's tables, and the unread ``kept_takes`` left to a default.

Same constraint as the sibling migration tests: Alembic's full chain does not run on SQLite,
so the schema is built from ``Base.metadata``, stamped at a revision and walked down and up.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

import app.db.models  # noqa: F401  (populates Base.metadata with every table)
from app.core.database import Base
from tests.alembic_harness import columns_of, run_alembic, scalar, tables_of

pytestmark = pytest.mark.migration

TABLES_REVISION = "20261013_scene01"
DEFAULT_REVISION = "20261013_scene02"
PREVIOUS_REVISION = "20261012_spine02"

SCENE_TABLES = {"ir_scene_rehearsals"}
SESSION = "a0000000-0000-0000-0000-000000000001"
A_SESSION = (
    "INSERT INTO ir_sessions (id, project_id, pericope, language, status, messages,"
    " after_panorama, coverage_state, back_translation, created_at, updated_at)"
    " VALUES (:session, 'team-1', 'P03', 'pt', 'in_progress', '[]', 0, '{}', '{}',"
    " '2026-10-01 08:00:00', '2026-10-01 08:00:00')"
)


async def _execute(url: str, sql: str, params: dict | None = None) -> None:
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.execute(text(sql), params or {})
    await engine.dispose()


async def _at(tmp_path, revision: str) -> str:
    url = f"sqlite+aiosqlite:///{tmp_path / 'ir_scene_rehearsals_migration.db'}"
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    stamped = run_alembic(url, "stamp", revision)
    assert stamped.returncode == 0, stamped.stderr
    return url


async def test_the_scene_rehearsal_table_comes_and_goes_with_its_migration(tmp_path) -> None:
    url = await _at(tmp_path, TABLES_REVISION)
    down = run_alembic(url, "downgrade", PREVIOUS_REVISION)
    assert down.returncode == 0, down.stderr
    assert not SCENE_TABLES & await tables_of(url)

    up = run_alembic(url, "upgrade", TABLES_REVISION)

    assert up.returncode == 0, up.stderr
    assert await tables_of(url) >= SCENE_TABLES
    for table in SCENE_TABLES:
        assert {"session_id", "archive_id"} <= await columns_of(url, table), table
    assert {"n", "scene", "scene_said", "scene_guess", "sent_at", "duration_ms"} <= (
        await columns_of(url, "ir_scene_rehearsals")
    )

    down = run_alembic(url, "downgrade", PREVIOUS_REVISION)

    assert down.returncode == 0, down.stderr
    assert not SCENE_TABLES & await tables_of(url)


async def test_the_unread_kept_takes_column_fills_with_empty_when_a_session_leaves_it_out(
    tmp_path,
) -> None:
    url = await _at(tmp_path, DEFAULT_REVISION)
    down = run_alembic(url, "downgrade", TABLES_REVISION)
    assert down.returncode == 0, down.stderr
    with pytest.raises(IntegrityError):
        await _execute(url, A_SESSION, {"session": SESSION})

    up = run_alembic(url, "upgrade", DEFAULT_REVISION)

    assert up.returncode == 0, up.stderr
    await _execute(url, A_SESSION, {"session": SESSION})
    kept = await scalar(url, "SELECT kept_takes FROM ir_sessions WHERE id = :s", {"s": SESSION})
    assert kept == "{}"
