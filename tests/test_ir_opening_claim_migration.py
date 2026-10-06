"""ENG-1451 — the session row carries the claim on its opening.

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

REVISION = "20261006_opcl01"
PREVIOUS_REVISION = "20261006_zera01"
CLAIM = {"opening_claim_turn_id", "opening_claimed_at"}

SESSION = "a0000000-0000-0000-0000-000000000001"
STORED = "SELECT pericope, language, status, messages FROM ir_sessions WHERE id = :id"
AS_STORED = ("P03", "pt", "in_progress", '[{"role": "guide", "text": "Eu sou o Guia."}]')


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
                " after_panorama, coverage_state, kept_takes, back_translation, created_at,"
                " updated_at) VALUES (:id, :pericope, :language, :status, :messages, 0,"
                " '{}', '{}', '{}', '2026-10-01 08:00:00', '2026-10-01 08:00:00')"
            ),
            dict(
                zip(("pericope", "language", "status", "messages"), AS_STORED, strict=True),
                id=SESSION,
            ),
        )
    await engine.dispose()


@pytest.fixture()
async def before_the_migration(tmp_path) -> str:
    url = f"sqlite+aiosqlite:///{tmp_path / 'ir_opening_claim_migration.db'}"
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


async def test_the_migration_adds_the_claims_two_columns_and_its_downgrade_removes_them(
    before_the_migration,
) -> None:
    url = before_the_migration
    assert not CLAIM & await columns_of(url, "ir_sessions")

    up = run_alembic(url, "upgrade", REVISION)

    assert up.returncode == 0, up.stderr
    assert await columns_of(url, "ir_sessions") >= CLAIM
    assert await _row(url) == AS_STORED
    for column in sorted(CLAIM):
        assert (
            await scalar(url, f"SELECT {column} FROM ir_sessions WHERE id = :id", {"id": SESSION})
            is None
        ), "uma sessao guardada antes ganhou uma reivindicacao que ninguem fez"

    down = run_alembic(url, "downgrade", PREVIOUS_REVISION)

    assert down.returncode == 0, down.stderr
    assert not CLAIM & await columns_of(url, "ir_sessions")
    assert await _row(url) == AS_STORED
