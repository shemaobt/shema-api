"""ENG-1392 — the session row says whether its turn claim is the opening's.

Same constraint as the sibling migration tests: Alembic's full chain does not run on SQLite,
so the schema is built from ``Base.metadata``, stamped at this revision and walked down, and a
session is written in the shape the previous revision stored it.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

import app.db.models  # noqa: F401  (populates Base.metadata with every table)
from app.core.database import Base
from tests.alembic_harness import columns_of, run_alembic, scalar

pytestmark = pytest.mark.migration

REVISION = "20261021_opfor01"
PREVIOUS_REVISION = "20261021_forced01"
COLUMN = "claimed_for_the_opening"

SESSION = "a0000000-0000-0000-0000-000000000001"
STORED = (
    "SELECT pericope, language, status, messages, opening_claim_turn_id FROM ir_sessions"
    " WHERE id = :id"
)
AS_STORED = ("P03", "pt", "in_progress", "[]", "abertura")


async def _row(url: str) -> tuple:
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        row = (await conn.execute(text(STORED), {"id": SESSION})).one()
    await engine.dispose()
    return tuple(row)


async def _stored(url: str) -> None:
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO ir_sessions (id, pericope, language, status, messages,"
                " after_panorama, coverage_state, back_translation, created_at,"
                " updated_at, opening_claim_turn_id, opening_claimed_at) VALUES (:id, :pericope,"
                " :language, :status, :messages, 0, '{}', '{}', '2026-10-01 08:00:00',"
                " '2026-10-01 08:00:00', :claim, '2026-10-01 08:00:00')"
            ),
            dict(
                zip(
                    ("pericope", "language", "status", "messages", "claim"),
                    AS_STORED,
                    strict=True,
                ),
                id=SESSION,
            ),
        )
    await engine.dispose()


@pytest.fixture()
async def before_the_migration(tmp_path) -> str:
    url = f"sqlite+aiosqlite:///{tmp_path / 'ir_claim_for_the_opening_migration.db'}"
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


async def test_the_migration_adds_whether_the_claim_is_the_openings_and_its_downgrade_removes_it(
    before_the_migration,
) -> None:
    url = before_the_migration
    assert COLUMN not in await columns_of(url, "ir_sessions")

    up = run_alembic(url, "upgrade", REVISION)

    assert up.returncode == 0, up.stderr
    assert COLUMN in await columns_of(url, "ir_sessions")
    assert await _row(url) == AS_STORED
    claimed = await scalar(url, f"SELECT {COLUMN} FROM ir_sessions WHERE id = :id", {"id": SESSION})
    assert claimed in (0, False), "uma reivindicacao guardada antes passou a ser da abertura"

    down = run_alembic(url, "downgrade", PREVIOUS_REVISION)

    assert down.returncode == 0, down.stderr
    assert COLUMN not in await columns_of(url, "ir_sessions")
    assert await _row(url) == AS_STORED
