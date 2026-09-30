"""ENG-1163 — a warning standing on a row moves out of the status and back.

Before this migration a warning was written as ``needs_person`` with ``halt_kind`` warning, and
that pair was the only record that one stood. After it the warning has its own column and
``needs_person`` means a blocking halt only, so every row still standing on a warning has to
leave the status for the column — or the room reads a stopped session that nothing stopped,
and the warning reads as the blocking halt it never was.

Same constraint as the sibling migration tests: Alembic's full chain does not run on SQLite,
so the schema is built from ``Base.metadata``, stamped at this revision and walked down, and
the rows are written in the shape the previous revision stored them.
"""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.db.models  # noqa: F401  (populates Base.metadata with every table)
from app.core.database import Base
from app.core.room_enums import HaltKind
from app.db.models.internalization_room import IRSessionStatus
from app.services.internalization_room import halt
from app.services.internalization_room.sessions import get_session, unattend
from tests.alembic_harness import columns_of, run_alembic, scalar

pytestmark = pytest.mark.migration

REVISION = "20260929_warn01"
PREVIOUS_REVISION = "20260925_halt01"

TABLE = "ir_sessions"
COLUMN = "warned_at"
OPENED = "2026-09-29 09:00:00"
CLOSED = "2026-09-29 10:00:00"
VISITED = "2026-09-29 09:30:00"


async def _row(
    url: str,
    status: str,
    halt_kind: str | None,
    ended_at: str | None,
    *,
    lifted: str | None = None,
) -> str:
    session_id = str(uuid.uuid4())
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO ir_sessions (id, pericope, status, messages, after_panorama,"
                " coverage_state, kept_takes, back_translation, halt_kind, ended_at,"
                " attended_at, attended_by, lifted_halt, created_at, updated_at) VALUES (:id,"
                " 'P01', :status, '[]', 0, '{}', '{}', '{}', :halt_kind, :ended_at, :visited,"
                " :visitor, :lifted, :opened, :opened)"
            ),
            {
                "id": session_id,
                "status": status,
                "halt_kind": halt_kind,
                "ended_at": ended_at,
                "visited": VISITED if lifted is not None else None,
                "visitor": "ana" if lifted is not None else None,
                "lifted": lifted,
                "opened": OPENED,
            },
        )
    await engine.dispose()
    return session_id


@pytest.fixture()
async def before_the_migration(tmp_path) -> dict[str, str]:
    url = f"sqlite+aiosqlite:///{tmp_path / 'ir_standing_warning_migration.db'}"
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    stamped = run_alembic(url, "stamp", REVISION)
    assert stamped.returncode == 0, stamped.stderr
    down = run_alembic(url, "downgrade", PREVIOUS_REVISION)
    assert down.returncode == 0, down.stderr
    return {
        "url": url,
        "warned": await _row(url, "needs_person", "warning", None),
        "warned_after_the_close": await _row(url, "needs_person", "warning", CLOSED),
        "blocked": await _row(url, "needs_person", "blocking", None),
        "halted_before_the_kind": await _row(url, "needs_person", None, None),
        "lifted": await _row(url, "in_progress", "warning", None),
        "visited_warning": await _row(url, "in_progress", "warning", None, lifted="warning"),
        "visited_block": await _row(url, "in_progress", "blocking", None, lifted="blocking"),
    }


async def _read(url: str, session_id: str) -> tuple[object, bool]:
    where = {"id": session_id}
    status = await scalar(url, f"SELECT status FROM {TABLE} WHERE id = :id", where)
    warned = await scalar(url, f"SELECT {COLUMN} FROM {TABLE} WHERE id = :id", where)
    return status, warned is not None


async def test_a_standing_warning_leaves_the_status_for_its_own_column(before_the_migration):
    url = before_the_migration["url"]

    up = run_alembic(url, "upgrade", REVISION)

    assert up.returncode == 0, up.stderr
    assert await _read(url, before_the_migration["warned"]) == ("in_progress", True), (
        "o aviso de antes da migração continuou parando a sala"
    )
    assert await _read(url, before_the_migration["warned_after_the_close"]) == ("done", True), (
        "o aviso numa passagem já fechada a devolveu como em andamento"
    )
    assert await _read(url, before_the_migration["blocked"]) == ("needs_person", False)
    assert await _read(url, before_the_migration["halted_before_the_kind"]) == (
        "needs_person",
        False,
    )
    assert await _read(url, before_the_migration["lifted"]) == ("in_progress", False), (
        "um aviso que já tinha saído voltou a valer"
    )
    assert await _read(url, before_the_migration["visited_warning"]) == ("in_progress", True)
    assert await _read(url, before_the_migration["visited_block"]) == ("in_progress", False)


async def _undo_the_visit(url: str, session_id: str) -> tuple[IRSessionStatus, HaltKind | None]:
    engine = create_async_engine(url)
    try:
        async with async_sessionmaker(engine, class_=AsyncSession)() as db:
            undone = await unattend(db, await get_session(db, session_id))
            return undone.status, halt.standing(undone)
    finally:
        await engine.dispose()


async def test_undoing_a_visit_made_before_the_migration_brings_back_what_it_lifted(
    before_the_migration,
):
    """A visit to a warning brings back a warning, never a blocking halt nobody raised."""
    url = before_the_migration["url"]
    assert run_alembic(url, "upgrade", REVISION).returncode == 0

    assert await _undo_the_visit(url, before_the_migration["visited_warning"]) == (
        IRSessionStatus.IN_PROGRESS,
        HaltKind.WARNING,
    ), "desfazer uma visita a um aviso de antes da migração parava a sala com um bloqueio"
    assert await _undo_the_visit(url, before_the_migration["visited_block"]) == (
        IRSessionStatus.NEEDS_PERSON,
        HaltKind.BLOCKING,
    )


async def test_the_downgrade_puts_every_standing_warning_back_in_the_status(before_the_migration):
    url = before_the_migration["url"]
    assert run_alembic(url, "upgrade", REVISION).returncode == 0

    down = run_alembic(url, "downgrade", PREVIOUS_REVISION)

    assert down.returncode == 0, down.stderr
    assert COLUMN not in await columns_of(url, TABLE)
    where = "SELECT status FROM ir_sessions WHERE id = :id"
    for name, status in {
        "warned": "needs_person",
        "warned_after_the_close": "needs_person",
        "blocked": "needs_person",
        "halted_before_the_kind": "needs_person",
        "lifted": "in_progress",
        "visited_warning": "in_progress",
        "visited_block": "in_progress",
    }.items():
        assert await scalar(url, where, {"id": before_the_migration[name]}) == status, name
    lifted = "SELECT lifted_halt FROM ir_sessions WHERE id = :id"
    for name, kind_lifted in {"visited_warning": "warning", "visited_block": "blocking"}.items():
        assert await scalar(url, lifted, {"id": before_the_migration[name]}) == kind_lifted, name
    kind = "SELECT halt_kind FROM ir_sessions WHERE id = :id"
    for name in ("warned", "warned_after_the_close"):
        assert await scalar(url, kind, {"id": before_the_migration[name]}) == "warning", (
            f"{name}: o aviso voltou como uma parada de outro tipo"
        )
