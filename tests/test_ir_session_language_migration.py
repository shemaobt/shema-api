"""ENG-662 — the column arrives, leaves, and comes back holding the floor.

Same constraint as the sibling migration tests: Alembic's full chain does not run on SQLite,
so this exercises the one migration under test. The schema is built from ``Base.metadata`` —
the post-migration shape — stamped as applied, filled with rows, then walked down and back up.

The backfill is the half worth watching, and it is a backfill that deliberately does not
happen. Every row written before this migration was a Portuguese session, and writing ``pt``
into them would make the floor depend on when a row was written — which is exactly the defect
the whole change exists to remove. A session's language decides only turns it has not taken
yet, and the app re-opens its sessions on restart.
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

REVISION = "20260831_lang01"
PREVIOUS_REVISION = "20260828_seg01"

TABLE = "ir_sessions"
OPENED = "2026-08-31 09:00:00"


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
                " coverage_state, kept_takes, back_translation, created_at, updated_at)"
                " VALUES (:id, 'P01', 'in_progress', '[]', 0, '{}', '{}', '{}', :opened, :opened)"
            ),
            {"id": session_id, "opened": OPENED},
        )
    await engine.dispose()
    return session_id


async def _columns(database_url: str, table: str) -> set[str]:
    engine = create_async_engine(database_url)
    async with engine.connect() as conn:
        columns = await conn.run_sync(lambda sync: inspect(sync).get_columns(table))
    await engine.dispose()
    return {c["name"] for c in columns}


async def _scalar(database_url: str, sql: str, params: dict) -> object:
    engine = create_async_engine(database_url)
    async with engine.connect() as conn:
        value = (await conn.execute(text(sql), params)).scalar_one_or_none()
    await engine.dispose()
    return value


@pytest.fixture()
async def applied_database(tmp_path) -> dict[str, str]:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'session_language_migration.db'}"
    session_id = await _build_and_seed(database_url)

    stamped = _run_alembic(database_url, "stamp", REVISION)
    assert stamped.returncode == 0, stamped.stderr

    return {"url": database_url, "session": session_id}


async def test_the_column_goes_away_on_downgrade_and_comes_back_on_upgrade(applied_database):
    url = applied_database["url"]

    assert "language" in await _columns(url, TABLE)

    down = _run_alembic(url, "downgrade", PREVIOUS_REVISION)
    assert down.returncode == 0, down.stderr
    assert "language" not in await _columns(url, TABLE)

    up = _run_alembic(url, "upgrade", REVISION)
    assert up.returncode == 0, up.stderr
    assert "language" in await _columns(url, TABLE)


async def test_a_row_written_before_the_column_existed_reads_as_the_floor(applied_database):
    """O piso é uma coisa só. Escrever `pt` nas linhas antigas faria o idioma padrão
    depender da data em que a linha foi criada, que é o defeito que isto remove."""
    url = applied_database["url"]

    assert _run_alembic(url, "downgrade", PREVIOUS_REVISION).returncode == 0
    assert _run_alembic(url, "upgrade", REVISION).returncode == 0

    spoken = await _scalar(
        url, "SELECT language FROM ir_sessions WHERE id = :id", {"id": applied_database["session"]}
    )
    assert spoken == "en"


async def test_the_round_trip_keeps_every_session(applied_database):
    url = applied_database["url"]

    assert _run_alembic(url, "downgrade", PREVIOUS_REVISION).returncode == 0
    assert _run_alembic(url, "upgrade", REVISION).returncode == 0

    assert await _scalar(url, f"SELECT count(*) FROM {TABLE}", {}) == 1
