"""Sessions standing at each station of the room, built through the room's own write paths.

Shared by the cases that read a station from the team's sessions, the halted-rooms queue, the
team's card and the pericopes rail, which is why it is here and not in any of them. Fixtures
never travel, so each module keeps its own few lines calling these.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRRelease, IRSession, IRTakeKind
from app.services.internalization_room import sessions as room
from tests.baker import keep_a_take
from tests.release_harness import (
    checked_telling_back,
    one_stretch,
    told_back_with_an_open_finding,
)

CONVERSATION = "conversation"
REHEARSAL = "rehearsal"
TELLING_BACK = "telling_back"
FINDINGS = "findings"
APPROVED = "approved"

P = "P03"


async def a_conversation(db: AsyncSession, team, *, pericope: str = P) -> IRSession:
    session = await room.create_session(db, pericope=pericope, project_id=team.id)
    return await room.append_exchange(db, session, team_utterance="oi", guide_response="ok")


async def a_rehearsal(db: AsyncSession, team, *, pericope: str = P) -> IRSession:
    session = await a_conversation(db, team, pericope=pericope)
    await keep_a_take(db, session, kind=IRTakeKind.ENSAIO)
    return session


async def a_telling_back(db: AsyncSession, team, *, pericope: str = P) -> IRSession:
    session = await a_rehearsal(db, team, pericope=pericope)
    await one_stretch(db, session)
    return session


async def a_telling_back_with_an_open_finding(
    db: AsyncSession, team, *, pericope: str = P
) -> IRSession:
    session = await a_rehearsal(db, team, pericope=pericope)
    state = await told_back_with_an_open_finding(db, session)
    await room.save_back_translation(db, session, state)
    return session


async def a_telling_back_with_every_finding_cleared(
    db: AsyncSession, team, *, pericope: str = P
) -> IRSession:
    session = await a_rehearsal(db, team, pericope=pericope)
    state = await checked_telling_back(db, session)
    await room.save_back_translation(db, session, state)
    return session


async def having_been_released(
    db: AsyncSession, session: IRSession, *, version: int = 1
) -> IRRelease:
    release = IRRelease(
        session_id=session.id,
        project_id=session.project_id,
        pericope=session.pericope,
        version=version,
        package_sha256=f"{version:064d}",
        packet={},
    )
    db.add(release)
    await db.commit()
    return release


async def an_approved_session(db: AsyncSession, team, *, pericope: str = P, version: int = 1):
    session = await a_telling_back(db, team, pericope=pericope)
    await having_been_released(db, session, version=version)
    return session
