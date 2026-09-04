"""ENG-609 — the three columns a facilitator's visit is recorded in travel both ways.

Same constraint as the sibling migration tests: Alembic's full chain does not run on SQLite —
the first migration in the tree writes a ``DEFAULT now()`` SQLite rejects — so this exercises
the one migration under test. The schema is built from ``Base.metadata``, which is the
post-migration shape, stamped as applied, filled with a row, then walked down and back up.

There is no backfill and there must not be one. ``attended_at`` and ``attended_by`` are the
record of a visit that happened, so inventing one for every existing row would be inventing
the visit. ``halt_kind`` is the kind of the *last* halt, and for a row halted before this
migration nobody wrote down which kind it was — the read side answers ``blocking`` for a
still-halted row with no kind, which is the conservative reading and belongs there rather than
in a write that would make it indistinguishable from a kind somebody recorded.
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

REVISION = "20260904_att01"
PREVIOUS_REVISION = "20260904_devnp"

TABLE = "ir_sessions"
NEW_COLUMNS = {"attended_at", "attended_by", "halt_kind"}
OPENED = "2026-09-04 09:00:00"


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
                " VALUES (:id, 'P01', 'needs_person', '[]', 0, '{}', '{}', '{}', :opened, :opened)"
            ),
            {"id": session_id, "opened": OPENED},
        )
    await engine.dispose()
    return session_id


async def _columns(database_url: str) -> set[str]:
    engine = create_async_engine(database_url)
    async with engine.connect() as conn:
        columns = await conn.run_sync(lambda sync: inspect(sync).get_columns(TABLE))
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
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'ir_attended_migration.db'}"
    session_id = await _build_and_seed(database_url)

    stamped = _run_alembic(database_url, "stamp", REVISION)
    assert stamped.returncode == 0, stamped.stderr

    return {"url": database_url, "session": session_id}


async def test_the_columns_go_away_on_downgrade_and_come_back_on_upgrade(applied_database):
    url = applied_database["url"]

    assert await _columns(url) >= NEW_COLUMNS

    down = _run_alembic(url, "downgrade", PREVIOUS_REVISION)
    assert down.returncode == 0, down.stderr
    assert NEW_COLUMNS.isdisjoint(await _columns(url)), (
        "o downgrade deixou colunas para trás, e um upgrade seguinte falha ao recriá-las"
    )

    up = _run_alembic(url, "upgrade", REVISION)
    assert up.returncode == 0, up.stderr
    assert await _columns(url) >= NEW_COLUMNS


async def test_a_room_halted_before_the_migration_keeps_its_halt_and_gains_no_visit(
    applied_database,
):
    """Nenhuma linha antiga ganha uma visita que não houve, nem perde a parada que tem."""
    url = applied_database["url"]

    assert _run_alembic(url, "downgrade", PREVIOUS_REVISION).returncode == 0
    assert _run_alembic(url, "upgrade", REVISION).returncode == 0

    where = {"id": applied_database["session"]}
    assert await _scalar(url, "SELECT status FROM ir_sessions WHERE id = :id", where) == (
        "needs_person"
    )
    for column in ("attended_at", "attended_by", "halt_kind"):
        assert await _scalar(url, f"SELECT {column} FROM ir_sessions WHERE id = :id", where) is None


async def test_the_round_trip_keeps_every_session(applied_database):
    url = applied_database["url"]

    assert _run_alembic(url, "downgrade", PREVIOUS_REVISION).returncode == 0
    assert _run_alembic(url, "upgrade", REVISION).returncode == 0

    assert await _scalar(url, f"SELECT count(*) FROM {TABLE}", {}) == 1
