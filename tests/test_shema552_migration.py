"""OBT-552 — every project id becomes an opaque UUID, and the move is reversible.

Same constraint as the other migration tests: Alembic's full chain does not run on SQLite, so this
exercises the one revision under test. The schema is built from ``Base.metadata`` — the
post-migration shape, append-only triggers included — then the mapping table is dropped and the
database stamped at the parent, filled with a slugged project and its children, and walked up
and back down.

What is worth proving is not that a table appeared. It is that **no id names a place after the
upgrade**, that every child — the append-only ones included — still points at its project,
that a project already holding a UUID is left alone, and that the downgrade gives the slug back
with everything still attached.
"""

import os
import subprocess
import sys
import uuid
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

import app.db.models  # noqa: F401  (populates Base.metadata with every table)
from app.core.database import Base
from app.db.models.shema import ShemaProject
from app.db.models.shema_enums import ShemaRegionKey

pytestmark = pytest.mark.migration

REPO_ROOT = Path(__file__).resolve().parent.parent

REVISION = "20261001_shema552"
PREVIOUS_REVISION = "20260930_rr13"

SLUG = "sa-di-of-high-egypt"
MINTED = str(uuid.uuid4())
USER = str(uuid.uuid4())


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


async def _build_and_seed(database_url: str) -> None:
    engine = create_async_engine(database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("DROP TABLE shema_project_rekeys"))
    async with AsyncSession(engine) as session:
        for project_id in (SLUG, MINTED):
            session.add(
                ShemaProject(
                    id=project_id,
                    language_name=f"Lingua {project_id[:4]}",
                    region_key=ShemaRegionKey.OTHER,
                )
            )
        await session.commit()
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO shema_progress_history (id, project_id, entry_date)"
                " VALUES (:id, :project, :day)"
            ),
            {"id": str(uuid.uuid4()), "project": SLUG, "day": date(2026, 9, 1)},
        )
        await conn.execute(
            text("INSERT INTO shema_notification_reads (user_id, entry_id) VALUES (:user, :entry)"),
            {"user": USER, "entry": f"stale:{SLUG}:2026-09-01"},
        )
        await conn.execute(
            text(
                "INSERT INTO shema_notification_prefs (user_id, custom_project_ids)"
                " VALUES (:user, :ids)"
            ),
            {"user": USER, "ids": f'["{SLUG}", "{MINTED}"]'},
        )
    await engine.dispose()


async def _rows(database_url: str, sql: str) -> list[tuple]:
    engine = create_async_engine(database_url)
    async with engine.connect() as conn:
        rows = [tuple(row) for row in (await conn.execute(text(sql))).all()]
    await engine.dispose()
    return rows


def _is_minted(value: str) -> bool:
    try:
        return str(uuid.UUID(value)) == value
    except ValueError:
        return False


@pytest.fixture()
async def database(tmp_path) -> str:
    url = f"sqlite+aiosqlite:///{tmp_path / 'shema552.db'}"
    await _build_and_seed(url)
    stamped = _run_alembic(url, "stamp", PREVIOUS_REVISION)
    assert stamped.returncode == 0, stamped.stderr
    return url


async def test_no_project_id_names_a_place_after_the_upgrade(database) -> None:
    up = _run_alembic(database, "upgrade", REVISION)
    assert up.returncode == 0, up.stderr

    ids = {row[0] for row in await _rows(database, "SELECT id FROM shema_projects")}
    assert all(_is_minted(project_id) for project_id in ids)
    assert MINTED in ids, "a project already holding a UUID was moved"

    [(old, new)] = await _rows(database, "SELECT old_id, new_id FROM shema_project_rekeys")
    assert old == SLUG and new in ids


async def test_every_child_follows_its_project_the_append_only_ones_included(database) -> None:
    assert _run_alembic(database, "upgrade", REVISION).returncode == 0
    [(new,)] = await _rows(database, "SELECT new_id FROM shema_project_rekeys")

    assert await _rows(database, "SELECT project_id FROM shema_progress_history") == [(new,)]
    [(prefs,)] = await _rows(database, "SELECT custom_project_ids FROM shema_notification_prefs")
    assert SLUG not in prefs and new in prefs and MINTED in prefs
    assert await _rows(database, "SELECT entry_id FROM shema_notification_reads") == [
        (f"stale:{new}:2026-09-01",)
    ]


async def test_the_history_is_still_append_only_after_the_move(database) -> None:
    assert _run_alembic(database, "upgrade", REVISION).returncode == 0

    engine = create_async_engine(database)
    with pytest.raises(Exception, match="append-only"):
        async with engine.begin() as conn:
            await conn.execute(text("UPDATE shema_progress_history SET translated_units = 1"))
    await engine.dispose()


async def test_the_downgrade_gives_the_slug_back_with_everything_attached(database) -> None:
    assert _run_alembic(database, "upgrade", REVISION).returncode == 0

    down = _run_alembic(database, "downgrade", PREVIOUS_REVISION)
    assert down.returncode == 0, down.stderr

    ids = {row[0] for row in await _rows(database, "SELECT id FROM shema_projects")}
    assert ids == {SLUG, MINTED}
    assert await _rows(database, "SELECT project_id FROM shema_progress_history") == [(SLUG,)]
    [(prefs,)] = await _rows(database, "SELECT custom_project_ids FROM shema_notification_prefs")
    assert SLUG in prefs and MINTED in prefs
    assert await _rows(database, "SELECT entry_id FROM shema_notification_reads") == [
        (f"stale:{SLUG}:2026-09-01",)
    ]
    tables = await _rows(
        database,
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'shema_project_rekeys'",
    )
    assert tables == []
