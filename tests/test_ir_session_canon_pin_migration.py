"""ENG-1219 — a session stored before the pin had a column keeps the canon the room serves.

Same constraint as the sibling migration tests: the schema is built from ``Base.metadata``,
stamped at this revision and walked down, and the rows are written in the previous shape.
"""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

import app.db.models  # noqa: F401  (populates Base.metadata with every table)
from app.core.database import Base
from app.services.internalization_room.canon.kept import deployed_pin
from tests.alembic_harness import columns_of, run_alembic, scalar

pytestmark = pytest.mark.migration

REVISION = "20261007_keep01"
PREVIOUS_REVISION = "20261006_opcl01"


async def _row(url: str, status: str) -> str:
    session_id = str(uuid.uuid4())
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO ir_sessions (id, pericope, status, messages, after_panorama,"
                " coverage_state, kept_takes, back_translation, created_at, updated_at)"
                " VALUES (:id, 'P03', :status, '[]', 0, '{}', '{}', '{}',"
                " '2026-10-07 09:00:00', '2026-10-07 09:00:00')"
            ),
            {"id": session_id, "status": status},
        )
    await engine.dispose()
    return session_id


@pytest.fixture()
async def before_the_migration(tmp_path) -> dict[str, str]:
    url = f"sqlite+aiosqlite:///{tmp_path / 'ir_session_canon_pin_migration.db'}"
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
        "working": await _row(url, "in_progress"),
        "done": await _row(url, "done"),
    }


async def test_every_stored_session_keeps_the_canon_the_room_serves_when_the_column_lands(
    before_the_migration,
):
    url = before_the_migration["url"]

    up = run_alembic(url, "upgrade", REVISION)

    assert up.returncode == 0, up.stderr
    for name in ("working", "done"):
        pin = await scalar(
            url,
            "SELECT canon_pin FROM ir_sessions WHERE id = :id",
            {"id": before_the_migration[name]},
        )
        assert pin == deployed_pin(), (
            f"a sessão {name} ficou sem canon e seguiria cada nova publicação"
        )


async def test_walking_down_takes_the_column_away(before_the_migration):
    url = before_the_migration["url"]
    assert run_alembic(url, "upgrade", REVISION).returncode == 0

    down = run_alembic(url, "downgrade", PREVIOUS_REVISION)

    assert down.returncode == 0, down.stderr
    assert "canon_pin" not in await columns_of(url, "ir_sessions")
