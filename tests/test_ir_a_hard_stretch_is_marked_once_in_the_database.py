"""One mark per stretch is the database's promise, and the row and the halt are one write.

ENG-869 made the ask once by reading the table before writing to it. A read before a write is
not a guarantee: two empty tellings of one stretch landing together both find no mark, both
write one, and each calls the halt — which clears `attended_at`, `attended_by` and
`person_arrived_at`, the record that a facilitator already walked to the room. The unique index
is the guarantee; the second writer's conflict is swallowed and it asks for nobody.

And the captured path committed the stretch row before the mark, so a failure between them left
a stretch standing at the number with no mark. The two are one fact and land in one transaction.

The ENG-869 cases go on holding; this file adds what the database and the transaction promise.
The room is built here rather than imported, which is this repository's pattern for a test
module that needs one: a fixture cannot be imported under the name a test takes it by without
the lint reading the parameter as a redefinition.
"""

from __future__ import annotations

import uuid
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.db.models  # noqa: F401  (populates Base.metadata with every table)
from app.core.database import Base
from app.core.enums import ProjectRole
from app.db.models.internalization_room import IRHardStretch, IRSegment
from app.services.internalization_room.sessions import RETELLS_BEFORE_A_WARNING, create_session
from tests.baker import (
    grant_facilitator_app_role,
    make_language,
    make_project,
    make_project_user_access,
    make_user,
)
from tests.test_ir_a_hard_stretch_is_marked_once import (
    DESK,
    DEVICE,
    IR,
    ROOM_KEY,
    SLICES,
    Facilitator,
    P,
    _a_session,
    _attend,
    _current,
    _marks,
    _MemoryStore,
    _rehearse,
    _row,
    _tell,
    _told,
    _voice,
)
from tests.test_ir_a_release_is_a_numbered_row import _indexes, _run_alembic

REVISION = "20260911_hard02"
PREVIOUS_REVISION = "20260910_seg02"
TABLE = "ir_hard_stretches"
UNIQUE_INDEX = "uq_ir_hard_stretches_session_segment"
SEEDED_MARK = "9a1d0c3e-77b2-4c1e-8f0a-2b3c4d5e6f70"


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    """The room and the Desk on one app: a mark is written on one side and read on the other.

    `client.said` queues what the transcriber will answer, one entry per capture. An entry of
    `""` is the outage the room cannot tell from silence.
    """
    from fastapi import FastAPI

    from app.api.facilitator.teams import facilitator_teams_router
    from app.api.internalization_room import back_translation as bt_api
    from app.api.internalization_room import router as room_router
    from app.api.internalization_room import segments as segments_api
    from app.api.internalization_room import sessions as sessions_api
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers
    from app.services.internalization_room import takes as takes_service

    monkeypatch.setattr(get_settings(), "internalization_room_api_key", ROOM_KEY, raising=False)
    monkeypatch.setattr(sessions_api.room, "synthesize_facilitator_speech", _voice)
    monkeypatch.setattr(bt_api.room, "synthesize_facilitator_speech", _voice)

    said: list[str] = []

    async def _transcribe(*_: Any, **__: Any) -> str:
        return said.pop(0) if said else "algo que a equipe contou"

    monkeypatch.setattr(bt_api, "heard", _transcribe)
    monkeypatch.setattr(segments_api, "heard", _transcribe)
    bucket = _MemoryStore()
    monkeypatch.setattr(takes_service, "_store", lambda *_, **__: bucket)

    test_app = FastAPI()
    test_app.include_router(room_router, prefix=IR)
    test_app.include_router(facilitator_teams_router, prefix=DESK)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        c.said = said  # type: ignore[attr-defined]
        yield c


@pytest.fixture()
async def facilitator(db_session: AsyncSession) -> Facilitator:
    from app.services.auth.issue_tokens import issue_tokens

    user = await make_user(db_session, email="ana@example.com")
    language = await make_language(db_session, name="Lingua P", code="lgp")
    project = await make_project(db_session, language.id, name="Equipe P")
    await make_project_user_access(db_session, project.id, user.id, role=ProjectRole.FACILITATOR)
    await grant_facilitator_app_role(db_session, user.id)
    access, _refresh = await issue_tokens(db_session, user)
    return Facilitator(user.id, project.id, {"Authorization": f"Bearer {access}"})


def _a_mark(session_id: str, segment_id: str) -> IRHardStretch:
    return IRHardStretch(
        id=str(uuid.uuid4()),
        session_id=session_id,
        segment_id=segment_id,
        tellings=RETELLS_BEFORE_A_WARNING,
    )


@pytest.mark.asyncio
async def test_two_marks_on_one_stretch_are_refused_by_the_database(
    db_session: AsyncSession,
) -> None:
    """The guarantee itself, asked of the database and of nothing else.

    Whatever the service does above it, the table may not hold one stretch twice: the second
    mark is the one whose halt erases the visit the first one already got.
    """
    session = await create_session(db_session, pericope=P)
    stretch_id = str(uuid.uuid4())

    db_session.add(_a_mark(session.id, stretch_id))
    await db_session.flush()
    db_session.add(_a_mark(session.id, stretch_id))

    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.fixture()
async def applied_database(tmp_path) -> str:
    """The post-migration schema with a mark in it, stamped as applied, ready to be walked.

    Alembic's full chain does not run on SQLite, so the sibling migration tests build the
    tables from ``Base.metadata`` and stamp the revision under test rather than upgrading into
    it. The seeded mark is what makes the round trip worth running: dropping and recreating an
    index must not take the rows it indexes with it.
    """
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'ir_hard_stretches_migration.db'}"
    engine = create_async_engine(database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(
            text(
                "INSERT INTO ir_hard_stretches (id, session_id, segment_id, tellings, crossed_at)"
                " VALUES (:id, 'uma-sessao', 'um-trecho', 3, '2026-09-11 09:00:00')"
            ),
            {"id": SEEDED_MARK},
        )
    await engine.dispose()

    stamped = _run_alembic(database_url, "stamp", REVISION)
    assert stamped.returncode == 0, stamped.stderr
    return database_url


@pytest.mark.asyncio
async def test_the_migration_creates_the_unique_index_both_ways(applied_database: str) -> None:
    down = _run_alembic(applied_database, "downgrade", PREVIOUS_REVISION)
    assert down.returncode == 0, down.stderr
    assert UNIQUE_INDEX not in await _indexes(applied_database, TABLE)

    up = _run_alembic(applied_database, "upgrade", REVISION)
    assert up.returncode == 0, up.stderr
    assert (await _indexes(applied_database, TABLE)).get(UNIQUE_INDEX) == (
        True,
        ["session_id", "segment_id"],
    ), (
        "the index has to be unique over exactly these two columns, in this order: the model "
        "declares it the same way and the CI runs `alembic check` after upgrading"
    )

    engine = create_async_engine(applied_database)
    async with engine.connect() as conn:
        kept = (
            await conn.execute(
                text("SELECT segment_id FROM ir_hard_stretches WHERE id = :id"),
                {"id": SEEDED_MARK},
            )
        ).scalar_one_or_none()
    await engine.dispose()

    assert kept == "um-trecho", "the round trip must not take the marks with the index"


async def _crossed_and_attended(client, db: AsyncSession, facilitator: Facilitator) -> str:
    """A stretch told until it crossed, and a facilitator who has answered the warning.

    The stamps this leaves are the record the second writer must not touch.
    """
    session_id = await _a_session(db, team_id=facilitator.team_id)
    take_id = await _rehearse(client, session_id)
    await _told(client, session_id, take_id, 1)
    for telling in range(RETELLS_BEFORE_A_WARNING - 1):
        answered = await _tell(
            client, session_id, take_id, 1, again=True, saying=f"de novo {telling}"
        )
        assert answered.status_code == 200, answered.text

    arrived = await client.post(
        f"{IR}/sessions/{session_id}/person-arrived", headers={"X-Room-Key": ROOM_KEY}
    )
    assert arrived.status_code == 200, arrived.text
    attended = await _attend(client, session_id, facilitator)
    assert attended.status_code == 200, attended.text
    return session_id


@pytest.mark.asyncio
async def test_the_second_writer_of_one_mark_loses_quietly(
    client, db_session: AsyncSession, facilitator: Facilitator
) -> None:
    """The fourth telling finds the mark already written and asks for nobody.

    It is the same thing the losing writer of a race sees — a row already there — reached by
    the road a test can drive. Both roads into the mark are taken: the telling nobody could make
    out, and the one that was captured. Neither may ask again, and neither may touch the visit.

    It is also the proof that swallowing the conflict inside a savepoint leaves the transaction
    usable on SQLite: the captured telling right after it writes and commits.
    """
    session_id = await _crossed_and_attended(client, db_session, facilitator)
    take_id = (await _current(db_session, session_id))[0].take_id
    attended = await _row(db_session, session_id)
    stamps = (attended.attended_at, attended.attended_by, attended.person_arrived_at)
    assert all(stamp is not None for stamp in stamps), (
        "the visit has to be on the row before anything below can mean the room kept it"
    )

    unheard = await _tell(client, session_id, take_id, 1, again=True)
    captured = await _tell(client, session_id, take_id, 1, again=True, saying="e mais uma vez")

    assert unheard.status_code == 200, unheard.text
    assert captured.status_code == 200, captured.text
    assert unheard.json()["needs_person"] is False
    assert captured.json()["needs_person"] is False
    assert len(await _marks(db_session, session_id)) == 1
    after = await _row(db_session, session_id)
    assert (after.attended_at, after.attended_by, after.person_arrived_at) == stamps, (
        "asking again would erase the record that a facilitator already walked to the room"
    )


@pytest.fixture()
def the_halt_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """The halt the mark calls, made to fail where it is called from.

    Patched in `hard_stretches`, because that is the name the call site reads: the module binds
    `mark_needs_person` by a bare import, so patching it on `sessions` reaches nothing. If the
    call site ever stops reading that name the two cases below fail loudly at `pytest.raises`,
    which is the right way for a seam to rot.
    """
    from app.services.internalization_room import hard_stretches

    async def _raise(*_, **__):
        raise RuntimeError("the halt could not be written")

    monkeypatch.setattr(hard_stretches, "mark_needs_person", _raise)


@pytest.fixture()
async def fresh(test_engine) -> AsyncSession:
    """A session of its own, so what is asserted is what was committed.

    The session the request died in still holds its writes and its identity map, and both would
    answer as though the telling had landed.
    """
    factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session


async def _every_stretch(db: AsyncSession, session_id: str) -> list[IRSegment]:
    return list(
        (await db.execute(select(IRSegment).where(IRSegment.session_id == session_id))).scalars()
    )


async def _told_twice(client, db: AsyncSession) -> tuple[str, str, str, int, set[str]]:
    """One stretch told twice: the next telling is the one that crosses.

    What the session holds, read as plain values while the session that owns it is still open.
    The request under test dies, its session is discarded, and a row object read back from it
    afterwards would go looking for its own columns with nobody left to fetch them.
    """
    session_id = await _a_session(db)
    take_id = await _rehearse(client, session_id)
    await _told(client, session_id, take_id, 1)
    answered = await _tell(client, session_id, take_id, 1, again=True, saying="a segunda vez")
    assert answered.status_code == 200, answered.text

    rows = await _every_stretch(db, session_id)
    standing = next(row for row in rows if row.superseded_at is None)
    return session_id, take_id, standing.id, standing.tellings, {row.id for row in rows}


async def _nothing_of_that_telling_landed(
    fresh: AsyncSession,
    session_id: str,
    stretch_id: str,
    tellings: int,
    before: set[str],
) -> None:
    """No version of the stretch, no count, no mark: the telling left nothing behind.

    Nothing here about the audio. The bytes are stored before anything is asked of them and are
    committed on their own, deliberately, so the retro take of the failed telling outlives it —
    a transcriber that times out must not take the recording with it.
    """
    rows = await _every_stretch(fresh, session_id)
    current = [row for row in rows if row.superseded_at is None]
    marks = list(
        (
            await fresh.execute(select(IRHardStretch).where(IRHardStretch.session_id == session_id))
        ).scalars()
    )

    assert [row.id for row in current] == [stretch_id], (
        "the stretch the team is standing on is the one from before the telling that failed"
    )
    assert current[0].tellings == tellings
    assert {row.id for row in rows} == before, "the version of that telling must not be left"
    assert marks == []


@pytest.mark.asyncio
async def test_the_stretch_row_and_the_mark_land_together_on_the_telling_back_route(
    client, db_session: AsyncSession, fresh: AsyncSession, the_halt_fails: None
) -> None:
    """The crossing telling fails whole or lands whole, and here it fails.

    The halt raising out of the request is the contract: nothing between the route and the mark
    may swallow it, because a 500 with the row committed is the state this case forbids.
    """
    session_id, take_id, stretch_id, tellings, before = await _told_twice(client, db_session)

    with pytest.raises(RuntimeError):
        await _tell(client, session_id, take_id, 1, again=True, saying="a que cruza")

    await db_session.rollback()
    await _nothing_of_that_telling_landed(fresh, session_id, stretch_id, tellings, before)


@pytest.mark.asyncio
async def test_the_stretch_row_and_the_mark_land_together_on_the_replace_route(
    client, db_session: AsyncSession, fresh: AsyncSession, the_halt_fails: None
) -> None:
    """The same, through the route a correction of one stretch comes in by."""
    session_id, take_id, stretch_id, tellings, before = await _told_twice(client, db_session)
    starts, ends = SLICES[0]
    client.said.append("a que cruza")

    with pytest.raises(RuntimeError):
        await client.post(
            f"{IR}/sessions/{session_id}/segments/{stretch_id}/replace",
            headers={"X-Room-Key": ROOM_KEY, "X-Room-Device": DEVICE},
            data={"take_id": take_id, "starts_ms": str(starts), "ends_ms": str(ends)},
            files={"file": ("trecho.m4a", b"a equipe contou de novo", "audio/mp4")},
        )

    await db_session.rollback()
    await _nothing_of_that_telling_landed(fresh, session_id, stretch_id, tellings, before)
