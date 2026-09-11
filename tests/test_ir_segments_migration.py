"""The stretch table goes up and comes back down, on a database that already holds rows.

Same constraint as the other room migrations: Alembic's full chain does not run on SQLite, so
this exercises the one migration under test. The schema is built from ``Base.metadata`` — which
is the post-migration shape — stamped as applied, filled with rows, then walked down and back
up.

Two things are worth proving beyond "a table appears". The partial index is one: the rule that a
position belongs to one **current** stretch is what stops a replaced stretch and its replacement
both counting, and an index declared for only one database is a rule nobody can rely on. Walking
down and up again on a database with rows in it is the other — a downgrade that leaves the
session tables it never created scratched would be found here and nowhere else.
"""

import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

import app.db.models  # noqa: F401  (populates Base.metadata with every table)
from app.core.database import Base
from tests.alembic_harness import run_alembic, tables_of

REPO_ROOT = Path(__file__).resolve().parent.parent

REVISION = "20260828_seg01"
PREVIOUS_REVISION = "20260823_join4"
TABLE = "ir_segments"


async def _build_and_seed(database_url: str) -> dict[str, str]:
    """Every table, with one session and two stretches: one that counts, one replaced."""
    engine = create_async_engine(database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_id = str(uuid.uuid4())
    replaced_id = str(uuid.uuid4())
    current_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO ir_sessions (id, pericope, status, messages, after_panorama,"
                " coverage_state, kept_takes, back_translation, comprehension, created_at,"
                " updated_at) VALUES (:id, 'P01', 'in_progress', '[]', 0, '{}', '{}', '{}',"
                " '{}', :now, :now)"
            ),
            {"id": session_id, "now": now},
        )
        for segment_id, superseded_at, superseded_by in (
            (replaced_id, now, current_id),
            (current_id, None, None),
        ):
            await conn.execute(
                text(
                    "INSERT INTO ir_segments (id, session_id, ordinal, take_id, starts_ms,"
                    " ends_ms, pass_number, transcript, superseded_at, superseded_by_id,"
                    " created_at) VALUES (:id, :session_id, 1, 'ensaio-1', 0, 9000, 1,"
                    " 'o que a equipe contou', :superseded_at, :superseded_by, :now)"
                ),
                {
                    "id": segment_id,
                    "session_id": session_id,
                    "superseded_at": superseded_at,
                    "superseded_by": superseded_by,
                    "now": now,
                },
            )
    await engine.dispose()
    return {"session_id": session_id, "replaced": replaced_id, "current": current_id}


async def _rows(database_url: str, sql: str, params: dict) -> list:
    engine = create_async_engine(database_url)
    async with engine.connect() as conn:
        found = (await conn.execute(text(sql), params)).all()
    await engine.dispose()
    return list(found)


@pytest.fixture()
async def applied_database(tmp_path) -> dict[str, str]:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'segments_migration.db'}"
    seeded = await _build_and_seed(database_url)

    stamped = run_alembic(database_url, "stamp", REVISION)
    assert stamped.returncode == 0, stamped.stderr

    return {"url": database_url, **seeded}


async def test_the_table_goes_away_on_downgrade_and_comes_back_on_upgrade(
    applied_database,
) -> None:
    url = applied_database["url"]

    assert TABLE in await tables_of(url)

    down = run_alembic(url, "downgrade", PREVIOUS_REVISION)
    assert down.returncode == 0, down.stderr
    assert TABLE not in await tables_of(url)

    up = run_alembic(url, "upgrade", REVISION)
    assert up.returncode == 0, up.stderr
    assert TABLE in await tables_of(url)


async def test_the_session_rows_are_untouched_by_the_round_trip(applied_database) -> None:
    """The room's other tables are not this migration's to alter, and a shared database is
    not the place to find that out later."""
    url = applied_database["url"]

    assert run_alembic(url, "downgrade", PREVIOUS_REVISION).returncode == 0
    assert run_alembic(url, "upgrade", REVISION).returncode == 0

    kept = await _rows(
        url,
        "SELECT pericope, status FROM ir_sessions WHERE id = :id",
        {"id": applied_database["session_id"]},
    )
    assert kept == [("P01", "in_progress")]


async def test_one_position_belongs_to_one_current_stretch(applied_database) -> None:
    """A replaced stretch and its replacement share a position; only one of them counts.

    Written against the database the migration built rather than against the ORM, because the
    index is the migration's promise and a rule that lives only in Python is not one.
    """
    url = applied_database["url"]
    engine = create_async_engine(url)

    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO ir_segments (id, session_id, ordinal, take_id, starts_ms, ends_ms,"
                " pass_number, created_at) VALUES ('outro', :session_id, 2, 'ensaio-1', 9000,"
                " 21000, 1, :now)"
            ),
            {"session_id": applied_database["session_id"], "now": datetime.now(UTC)},
        )

    with pytest.raises(Exception, match="UNIQUE"):
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO ir_segments (id, session_id, ordinal, take_id, starts_ms,"
                    " ends_ms, pass_number, created_at) VALUES ('colide', :session_id, 2,"
                    " 'ensaio-1', 9000, 21000, 1, :now)"
                ),
                {"session_id": applied_database["session_id"], "now": datetime.now(UTC)},
            )
    await engine.dispose()


async def test_one_position_belongs_to_one_current_stretch_under_a_parent(
    applied_database,
) -> None:
    """The other half, and the reason there are two indexes rather than one.

    Siblings of a divided stretch carry a parent, so they fall under the index that names it;
    the case above carries none and falls under the index written for exactly that.
    """
    url = applied_database["url"]
    engine = create_async_engine(url)
    parent = applied_database["current"]

    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO ir_segments (id, session_id, parent_id, ordinal, take_id,"
                " starts_ms, ends_ms, pass_number, created_at) VALUES ('filho', :session_id,"
                " :parent, 1, 'ensaio-1', 0, 4000, 1, :now)"
            ),
            {
                "session_id": applied_database["session_id"],
                "parent": parent,
                "now": datetime.now(UTC),
            },
        )

    with pytest.raises(Exception, match="UNIQUE"):
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO ir_segments (id, session_id, parent_id, ordinal, take_id,"
                    " starts_ms, ends_ms, pass_number, created_at) VALUES ('colide',"
                    " :session_id, :parent, 1, 'ensaio-1', 0, 4000, 1, :now)"
                ),
                {
                    "session_id": applied_database["session_id"],
                    "parent": parent,
                    "now": datetime.now(UTC),
                },
            )
    await engine.dispose()
