"""ENG-1422 — the outside listeners' three tables come and go with their migration.

Same constraint as the sibling migration tests: Alembic's full chain does not run on SQLite,
so the schema is built from ``Base.metadata``, stamped at a revision and walked down and up.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

import app.db.models  # noqa: F401  (populates Base.metadata with every table)
from app.core.database import Base
from tests.alembic_harness import (
    indexes_of,
    run_alembic,
    scalar,
    tables_of,
    unique_constraints_of,
)

pytestmark = pytest.mark.migration

REVISION = "20261022_listen01"
PREVIOUS_REVISION = "20261022_extchk01"
UNIQUE = {
    "ir_external_listeners": ("uq_ir_external_listeners_check_number", ["check_id", "number"]),
    "ir_external_recordings": (
        "uq_ir_external_recordings_listener_sha256",
        ["listener_id", "sha256"],
    ),
    "ir_external_marks": ("uq_ir_external_marks_listener_segment", ["listener_id", "segment_id"]),
}
INDEXED = {
    "ir_external_listeners": ("check_id", "session_id"),
    "ir_external_recordings": ("listener_id", "session_id"),
    "ir_external_marks": ("listener_id", "session_id"),
}
SESSION = "a0000000-0000-0000-0000-000000001422"
A_SESSION = (
    "INSERT INTO ir_sessions (id, project_id, pericope, language, status, messages,"
    " after_panorama, coverage_state, back_translation, created_at, updated_at)"
    " VALUES (:session, 'team-1', 'P03', 'pt', 'in_progress', '[]', 0, '{}', '{}',"
    " '2026-10-01 08:00:00', '2026-10-01 08:00:00')"
)


async def _at(tmp_path, revision: str) -> str:
    url = f"sqlite+aiosqlite:///{tmp_path / 'ir_outside_listeners_migration.db'}"
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text(A_SESSION), {"session": SESSION})
    await engine.dispose()
    stamped = run_alembic(url, "stamp", revision)
    assert stamped.returncode == 0, stamped.stderr
    return url


async def test_the_outside_listeners_tables_come_and_go_with_their_migration(tmp_path) -> None:
    url = await _at(tmp_path, REVISION)
    down = run_alembic(url, "downgrade", PREVIOUS_REVISION)
    assert down.returncode == 0, down.stderr
    assert not set(UNIQUE) & set(await tables_of(url))

    up = run_alembic(url, "upgrade", REVISION)

    assert up.returncode == 0, up.stderr
    for table, (name, columns) in UNIQUE.items():
        assert (await unique_constraints_of(url, table)).get(name) == columns, table
        indexes = await indexes_of(url, table)
        for column in INDEXED[table]:
            assert indexes.get(f"ix_{table}_{column}") == (False, [column]), (table, column)

    down = run_alembic(url, "downgrade", PREVIOUS_REVISION)

    assert down.returncode == 0, down.stderr
    tables = set(await tables_of(url))
    assert not set(UNIQUE) & tables
    assert "ir_external_checks" in tables
    assert (
        await scalar(url, "SELECT pericope FROM ir_sessions WHERE id = :id", {"id": SESSION})
        == "P03"
    ), "a ida e volta não pode arranhar as tabelas que a migração não criou"
