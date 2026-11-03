"""ENG-1421 — the Checagem externa's table comes and goes with its migration.

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

REVISION = "20261022_extchk01"
PREVIOUS_REVISION = "20261021_opfor01"
TABLE = "ir_external_checks"
SESSION = "a0000000-0000-0000-0000-000000001421"
A_SESSION = (
    "INSERT INTO ir_sessions (id, project_id, pericope, language, status, messages,"
    " after_panorama, coverage_state, back_translation, created_at, updated_at)"
    " VALUES (:session, 'team-1', 'P03', 'pt', 'in_progress', '[]', 0, '{}', '{}',"
    " '2026-10-01 08:00:00', '2026-10-01 08:00:00')"
)


async def _at(tmp_path, revision: str) -> str:
    url = f"sqlite+aiosqlite:///{tmp_path / 'ir_external_check_migration.db'}"
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text(A_SESSION), {"session": SESSION})
    await engine.dispose()
    stamped = run_alembic(url, "stamp", revision)
    assert stamped.returncode == 0, stamped.stderr
    return url


async def test_the_external_check_table_comes_and_goes_with_its_migration(tmp_path) -> None:
    url = await _at(tmp_path, REVISION)
    down = run_alembic(url, "downgrade", PREVIOUS_REVISION)
    assert down.returncode == 0, down.stderr
    assert TABLE not in await tables_of(url)

    up = run_alembic(url, "upgrade", REVISION)

    assert up.returncode == 0, up.stderr
    assert TABLE in await tables_of(url)
    assert (await unique_constraints_of(url, TABLE)).get("uq_ir_external_checks_release") == [
        "release_id"
    ], "sem o único sobre a release, duas aberturas ao mesmo tempo deixam duas checagens"
    assert (await indexes_of(url, TABLE)).get("ix_ir_external_checks_session_id") == (
        False,
        ["session_id"],
    )

    down = run_alembic(url, "downgrade", PREVIOUS_REVISION)

    assert down.returncode == 0, down.stderr
    assert TABLE not in await tables_of(url)
    assert (
        await scalar(url, "SELECT pericope FROM ir_sessions WHERE id = :id", {"id": SESSION})
        == "P03"
    ), "a ida e volta não pode arranhar as tabelas que a migração não criou"
