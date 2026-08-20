"""ENG-450 — the column that records which passage a prepared opening was written for.

Same constraint as the sibling migration tests: Alembic's full chain does not run on SQLite,
so this exercises the one migration under test. The schema is built from `Base.metadata` —
the post-migration shape — stamped as applied, filled with rows, then walked down and back up.

A nullable column add has one thing worth watching and it is the round trip: `downgrade` drops
the column, and on SQLite that is a table rebuild rather than an `ALTER`. A rebuild that loses
the sessions would lose every conversation the room has ever had, which no test of the column
itself would notice.
"""

import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

import app.db.models  # noqa: F401  (populates Base.metadata with every table)
from app.core.database import Base

REPO_ROOT = Path(__file__).resolve().parent.parent

REVISION = "20260820_0003"
PREVIOUS_REVISION = "20260820_0002"

TABLE = "ir_sessions"
COLUMN = "prepared_pericope"
WHEN = "2026-08-20 00:00:00"


def _run_alembic(database_url: str, *argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "alembic", *argv],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "DATABASE_URL": database_url,
            "JWT_SECRET_KEY": "test-secret-for-pytest-only",
            "INNGEST_DEV": "1",
        },
        capture_output=True,
        text=True,
    )


async def _build_and_seed(database_url: str) -> str:
    engine = create_async_engine(database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_id = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO ir_sessions (id, pericope, status, messages, after_panorama,"
                " coverage_state, kept_takes, back_translation, prepared_speech,"
                " prepared_audio_key, prepared_pericope, created_at, updated_at)"
                " VALUES (:id, 'OV-Ruth', 'in_progress', '[]', 0, '{}', '{}', '{}',"
                " 'a primeira fala', 'tts/v/p02.mp3', 'P02', :now, :now)"
            ),
            {"id": session_id, "now": WHEN},
        )
    await engine.dispose()
    return session_id


@pytest.fixture()
async def applied_database(tmp_path):
    """A database at this revision, stamped rather than migrated up to it."""
    path = tmp_path / "prepared_pericope.db"
    url = f"sqlite+aiosqlite:///{path}"
    session_id = await _build_and_seed(url)

    stamped = _run_alembic(url, "stamp", REVISION)
    assert stamped.returncode == 0, stamped.stderr

    yield url, session_id


async def _columns(url: str) -> set[str]:
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        found = await conn.run_sync(
            lambda sync: {c["name"] for c in inspect(sync).get_columns(TABLE)}
        )
    await engine.dispose()
    return found


@pytest.mark.asyncio
async def test_the_column_goes_away_on_downgrade_and_comes_back_on_upgrade(applied_database):
    url, _session_id = applied_database

    down = _run_alembic(url, "downgrade", PREVIOUS_REVISION)
    assert down.returncode == 0, down.stderr
    assert COLUMN not in await _columns(url)

    up = _run_alembic(url, "upgrade", REVISION)
    assert up.returncode == 0, up.stderr
    assert COLUMN in await _columns(url)


@pytest.mark.asyncio
async def test_the_round_trip_leaves_the_sessions_alone(applied_database):
    """Dropping a column on SQLite rebuilds the table. The conversations have to survive it."""
    url, session_id = applied_database

    assert _run_alembic(url, "downgrade", PREVIOUS_REVISION).returncode == 0
    assert _run_alembic(url, "upgrade", REVISION).returncode == 0

    engine = create_async_engine(url)
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT pericope, prepared_speech, prepared_audio_key, prepared_pericope"
                    " FROM ir_sessions WHERE id = :id"
                ),
                {"id": session_id},
            )
        ).one()
    await engine.dispose()

    assert row.pericope == "OV-Ruth"
    assert row.prepared_speech == "a primeira fala"
    assert row.prepared_audio_key == "tts/v/p02.mp3"


@pytest.mark.asyncio
async def test_the_passage_a_line_was_written_for_does_not_survive_the_downgrade(
    applied_database,
):
    """It cannot, and that is the point: the column is where the fact lives.

    A round trip therefore leaves a prepared line with no passage recorded — and `hand_over`
    refuses such a line rather than guessing, which is why the downgrade is safe to run.
    """
    url, session_id = applied_database

    assert _run_alembic(url, "downgrade", PREVIOUS_REVISION).returncode == 0
    assert _run_alembic(url, "upgrade", REVISION).returncode == 0

    engine = create_async_engine(url)
    async with engine.connect() as conn:
        recorded = (
            await conn.execute(
                text("SELECT prepared_pericope FROM ir_sessions WHERE id = :id"),
                {"id": session_id},
            )
        ).scalar_one()
    await engine.dispose()

    assert recorded is None
