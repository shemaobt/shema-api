"""ENG-1765 — a session keeps its grain and the switch's time, and a take its set-aside stamp.

Same constraint as the sibling migration tests: Alembic's full chain does not run on SQLite,
so the schema is built from ``Base.metadata``, stamped at this revision and walked down, and the
rows are written in the shape the previous revision stored them.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

import app.db.models  # noqa: F401  (populates Base.metadata with every table)
from app.core.database import Base
from tests.alembic_harness import columns_of, run_alembic, scalar

pytestmark = pytest.mark.migration

REVISION = "20261022_grain01"
PREVIOUS_REVISION = "20261022_listen01"

SESSION = "a0000000-0000-0000-0000-000000000001"
TAKE = "b0000000-0000-0000-0000-000000000001"
AGAIN = "b0000000-0000-0000-0000-000000000002"
STORED_AT = "2026-10-01 08:00:00"


async def _insert_a_session_and_its_take(url: str) -> None:
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO ir_sessions (id, project_id, pericope, language, status, messages,"
                " after_panorama, coverage_state, back_translation, created_at, updated_at)"
                " VALUES (:session, 'team-1', 'P03', 'pt', 'in_progress', '[]', 0, '{}', '{}',"
                " :stored, :stored)"
            ),
            {"session": SESSION, "stored": STORED_AT},
        )
        await conn.execute(
            text(
                "INSERT INTO ir_takes (id, session_id, device_id, project_id, pericope, kind,"
                " scope, ordinal, storage_key, size_bytes, sha256, crc32c, content_type,"
                " created_at, recorded_at) VALUES (:take, :session, 'tablet-1', 'team-1', 'P03',"
                " 'ensaio', 'parte-1', 1, 'takes/x', 2048, 'aa', 'AAAAAAA=', 'audio/mp4',"
                " :stored, :stored)"
            ),
            {"take": TAKE, "session": SESSION, "stored": STORED_AT},
        )
    await engine.dispose()


@pytest.fixture()
async def before_the_migration(tmp_path) -> str:
    url = f"sqlite+aiosqlite:///{tmp_path / 'ir_grain_switch_migration.db'}"
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    stamped = run_alembic(url, "stamp", REVISION)
    assert stamped.returncode == 0, stamped.stderr
    down = run_alembic(url, "downgrade", PREVIOUS_REVISION)
    assert down.returncode == 0, down.stderr
    await _insert_a_session_and_its_take(url)
    return url


async def test_a_stored_session_and_take_read_as_never_switched(before_the_migration) -> None:
    url = before_the_migration

    up = run_alembic(url, "upgrade", REVISION)

    assert up.returncode == 0, up.stderr
    assert (
        await scalar(url, "SELECT grain FROM ir_sessions WHERE id = :id", {"id": SESSION}) is None
    )
    assert (
        await scalar(
            url, "SELECT grain_switched_at FROM ir_sessions WHERE id = :id", {"id": SESSION}
        )
        is None
    )
    assert (
        await scalar(url, "SELECT set_aside_at FROM ir_takes WHERE id = :id", {"id": TAKE}) is None
    ), "uma tomada guardada antes nascia deixada de lado por uma troca que não houve"


async def test_the_same_bytes_kept_again_beside_their_set_aside_take_are_a_second_row(
    before_the_migration,
) -> None:
    url = before_the_migration
    up = run_alembic(url, "upgrade", REVISION)
    assert up.returncode == 0, up.stderr
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE ir_takes SET set_aside_at = :stored WHERE id = :id"),
            {"stored": STORED_AT, "id": TAKE},
        )
        await conn.execute(
            text(
                "INSERT INTO ir_takes (id, session_id, device_id, project_id, pericope, kind,"
                " scope, ordinal, storage_key, size_bytes, sha256, crc32c, content_type,"
                " created_at, recorded_at) VALUES (:take, :session, 'tablet-1', 'team-1', 'P03',"
                " 'ensaio', 'parte-1', 1, 'takes/x', 2048, 'aa', 'AAAAAAA=', 'audio/mp4',"
                " :stored, :stored)"
            ),
            {"take": AGAIN, "session": SESSION, "stored": STORED_AT},
        )
    await engine.dispose()

    assert (
        await scalar(url, "SELECT count(*) FROM ir_takes WHERE session_id = :id", {"id": SESSION})
        == 2
    )


async def test_the_migration_walks_down(before_the_migration) -> None:
    url = before_the_migration
    up = run_alembic(url, "upgrade", REVISION)
    assert up.returncode == 0, up.stderr

    down = run_alembic(url, "downgrade", PREVIOUS_REVISION)

    assert down.returncode == 0, down.stderr
    assert {"grain", "grain_switched_at"}.isdisjoint(await columns_of(url, "ir_sessions"))
    assert "set_aside_at" not in await columns_of(url, "ir_takes")
    assert await scalar(url, "SELECT count(*) FROM ir_takes WHERE id = :id", {"id": TAKE}) == 1
