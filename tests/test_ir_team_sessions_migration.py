"""ENG-1236 — the backfill points each team's pericope and language at its latest session.

Same constraint as the sibling migration tests: Alembic's full chain does not run on SQLite,
so the schema is built from ``Base.metadata``, stamped at this revision and walked down, and
the sessions are written in the shape the previous revision stored them. The duplicates a team
already holds stay in history; only the pointer is new.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

import app.db.models  # noqa: F401  (populates Base.metadata with every table)
from app.core.database import Base
from tests.alembic_harness import run_alembic, scalar, tables_of

pytestmark = pytest.mark.migration

REVISION = "20261002_open01"
PREVIOUS_REVISION = "20261001_done01"

TEAM = "11111111-1111-1111-1111-111111111111"
OTHER_TEAM = "22222222-2222-2222-2222-222222222222"

#: (id, team, pericope, language, created_at, updated_at)
SESSIONS = (
    (
        "a0000000-0000-0000-0000-000000000001",
        TEAM,
        "P03",
        "pt",
        "2026-09-28 09:00:00",
        "2026-09-30 10:00:00",
    ),
    (
        "a0000000-0000-0000-0000-000000000002",
        TEAM,
        "P03",
        "pt",
        "2026-09-28 08:00:00",
        "2026-09-30 10:00:00",
    ),
    (
        "a0000000-0000-0000-0000-000000000003",
        TEAM,
        "P03",
        "pt",
        "2026-09-29 09:00:00",
        "2026-09-30 09:00:00",
    ),
    (
        "b0000000-0000-0000-0000-000000000001",
        TEAM,
        "P04",
        "pt",
        "2026-09-28 08:00:00",
        "2026-09-30 10:00:00",
    ),
    (
        "b0000000-0000-0000-0000-000000000002",
        TEAM,
        "P04",
        "pt",
        "2026-09-28 08:00:00",
        "2026-09-30 10:00:00",
    ),
    (
        "c0000000-0000-0000-0000-000000000001",
        TEAM,
        "P03",
        "en",
        "2026-09-28 08:00:00",
        "2026-09-28 08:00:00",
    ),
    (
        "d0000000-0000-0000-0000-000000000001",
        OTHER_TEAM,
        "P03",
        "pt",
        "2026-09-27 08:00:00",
        "2026-09-27 08:00:00",
    ),
    (
        "e0000000-0000-0000-0000-000000000001",
        None,
        "P03",
        "pt",
        "2026-10-01 08:00:00",
        "2026-10-01 08:00:00",
    ),
)

POINTERS = "SELECT project_id, pericope, language, session_id FROM ir_team_sessions"


async def _rows(url: str, sql: str) -> list[tuple]:
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        rows = (await conn.execute(text(sql))).all()
    await engine.dispose()
    return sorted(tuple(row) for row in rows)


async def _stored(url: str) -> None:
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        for session_id, team, pericope, language, created, updated in SESSIONS:
            await conn.execute(
                text(
                    "INSERT INTO ir_sessions (id, project_id, pericope, language, status,"
                    " messages, after_panorama, coverage_state, kept_takes, back_translation,"
                    " created_at, updated_at) VALUES (:id, :team, :pericope, :language,"
                    " 'in_progress', '[]', 0, '{}', '{}', '{}', :created, :updated)"
                ),
                {
                    "id": session_id,
                    "team": team,
                    "pericope": pericope,
                    "language": language,
                    "created": created,
                    "updated": updated,
                },
            )
    await engine.dispose()


@pytest.fixture()
async def before_the_migration(tmp_path) -> str:
    url = f"sqlite+aiosqlite:///{tmp_path / 'ir_team_sessions_migration.db'}"
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


async def test_the_backfill_points_each_teams_pericope_and_language_at_its_latest_session_and_leaves_every_stored_session_in_place(  # noqa: E501
    before_the_migration,
) -> None:
    url = before_the_migration

    up = run_alembic(url, "upgrade", REVISION)

    assert up.returncode == 0, up.stderr
    assert await _rows(url, POINTERS) == [
        (TEAM, "P03", "en", "c0000000-0000-0000-0000-000000000001"),
        (TEAM, "P03", "pt", "a0000000-0000-0000-0000-000000000001"),
        (TEAM, "P04", "pt", "b0000000-0000-0000-0000-000000000002"),
        (OTHER_TEAM, "P03", "pt", "d0000000-0000-0000-0000-000000000001"),
    ]
    assert await scalar(url, "SELECT count(*) FROM ir_sessions", {}) == len(SESSIONS)

    down = run_alembic(url, "downgrade", PREVIOUS_REVISION)

    assert down.returncode == 0, down.stderr
    assert "ir_team_sessions" not in await tables_of(url)
    assert await scalar(url, "SELECT count(*) FROM ir_sessions", {}) == len(SESSIONS)
