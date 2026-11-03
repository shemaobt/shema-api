"""ENG-1378 — the session keeps the retelling verdict of each of its turns.

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

REVISION = "20261019_retel01"
PREVIOUS_REVISION = "20261016_demo01"

SESSION = "a0000000-0000-0000-0000-000000000001"
STORED = (
    "SELECT pericope, language, status, messages, coverage_state,"
    " back_translation FROM ir_sessions WHERE id = :id"
)
AS_STORED = (
    "P03",
    "pt",
    "in_progress",
    '[{"role": "team", "text": "Noemi voltou com Rute"}]',
    '{"P03-S1": "engaged"}',
    '{"round": 1}',
)


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
                " updated_at) VALUES (:id, :pericope, :language, :status, :messages, 0,"
                " :coverage, :bt, '2026-10-01 08:00:00', '2026-10-01 08:00:00')"
            ),
            dict(
                zip(
                    ("pericope", "language", "status", "messages", "coverage", "bt"),
                    AS_STORED,
                    strict=True,
                ),
                id=SESSION,
            ),
        )
    await engine.dispose()


@pytest.fixture()
async def before_the_migration(tmp_path) -> str:
    url = f"sqlite+aiosqlite:///{tmp_path / 'ir_retellings_migration.db'}"
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


async def test_the_retellings_column_is_added_and_stored_sessions_keep_everything_they_had(
    before_the_migration,
) -> None:
    url = before_the_migration
    assert "retellings" not in await columns_of(url, "ir_sessions")

    up = run_alembic(url, "upgrade", REVISION)

    assert up.returncode == 0, up.stderr
    assert "retellings" in await columns_of(url, "ir_sessions")
    assert await _row(url) == AS_STORED
    assert (
        await scalar(url, "SELECT retellings FROM ir_sessions WHERE id = :id", {"id": SESSION})
        is None
    ), "uma sessão guardada antes não tinha veredito nenhum e ganhou um"

    down = run_alembic(url, "downgrade", PREVIOUS_REVISION)

    assert down.returncode == 0, down.stderr
    assert "retellings" not in await columns_of(url, "ir_sessions")
    assert await _row(url) == AS_STORED
