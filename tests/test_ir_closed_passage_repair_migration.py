"""ENG-1180 — a closed passage the old code left in progress goes back to done.

Same constraint as the sibling migration tests: Alembic's full chain does not run on SQLite,
so the schema is built from ``Base.metadata``, stamped at this revision and walked down, and
the rows are written in the shape the previous revision stored them.
"""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

import app.db.models  # noqa: F401  (populates Base.metadata with every table)
from app.core.database import Base
from tests.alembic_harness import run_alembic, scalar

pytestmark = pytest.mark.migration

REVISION = "20261001_done01"
PREVIOUS_REVISION = "20260930_idem01"

OPENED = "2026-09-30 09:00:00"
CLOSED = "2026-09-30 10:00:00"
STATUS = "SELECT status FROM ir_sessions WHERE id = :id"


async def _row(url: str, status: str, ended_at: str | None) -> str:
    session_id = str(uuid.uuid4())
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO ir_sessions (id, pericope, status, messages, after_panorama,"
                " coverage_state, kept_takes, back_translation, ended_at, created_at,"
                " updated_at) VALUES (:id, 'P01', :status, '[]', 0, '{}', '{}', '{}',"
                " :ended_at, :opened, :opened)"
            ),
            {"id": session_id, "status": status, "ended_at": ended_at, "opened": OPENED},
        )
    await engine.dispose()
    return session_id


@pytest.fixture()
async def before_the_migration(tmp_path) -> dict[str, str]:
    url = f"sqlite+aiosqlite:///{tmp_path / 'ir_closed_passage_repair_migration.db'}"
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    stamped = run_alembic(url, "stamp", REVISION)
    assert stamped.returncode == 0, stamped.stderr
    down = run_alembic(url, "downgrade", PREVIOUS_REVISION)
    assert down.returncode == 0, down.stderr
    return {
        "url": url,
        "closed_after_a_visit": await _row(url, "in_progress", CLOSED),
        "closed_after_a_turn": await _row(url, "in_progress", CLOSED),
        "honest": await _row(url, "in_progress", None),
        "still_halted": await _row(url, "needs_person", CLOSED),
    }


async def test_the_migration_repairs_the_rows_the_old_code_left_wrong(before_the_migration):
    url = before_the_migration["url"]

    up = run_alembic(url, "upgrade", REVISION)

    assert up.returncode == 0, up.stderr
    for name in ("closed_after_a_visit", "closed_after_a_turn"):
        assert await scalar(url, STATUS, {"id": before_the_migration[name]}) == "done", (
            f"{name}: a passagem fechada continuou em andamento"
        )
    assert await scalar(url, STATUS, {"id": before_the_migration["honest"]}) == "in_progress"
    assert await scalar(url, STATUS, {"id": before_the_migration["still_halted"]}) == (
        "needs_person"
    ), "a migração apagou uma parada que ainda está de pé"

    down = run_alembic(url, "downgrade", PREVIOUS_REVISION)

    assert down.returncode == 0, down.stderr
    for name in ("closed_after_a_visit", "closed_after_a_turn"):
        assert await scalar(url, STATUS, {"id": before_the_migration[name]}) == "done", name
    assert await scalar(url, STATUS, {"id": before_the_migration["honest"]}) == "in_progress"
