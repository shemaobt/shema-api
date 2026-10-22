"""The Desk's «Sessões»: the live, entered sessions of every team the reader may read (ENG-1192).

Read-only, newest activity first, paged by a keyset cursor the way the inbox is. Each item
reads the same beads and the same state the team's own session card reads.
"""

from __future__ import annotations

import base64
import binascii
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import ColumnElement, and_, or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import SessionState
from app.core.exceptions import NotFoundError, ValidationError
from app.db.models.auth import User
from app.db.models.internalization_room import IRRelease, IRSession, IRTake, IRTakeKind
from app.db.models.project import Project
from app.models.internalization_room_desk_sessions import (
    DeskSession,
    DeskSessionsPage,
    DeskSessionState,
)
from app.services.internalization_room.canon.parse_map import served_maps
from app.services.internalization_room.conversation import guide_turns_of
from app.services.internalization_room.coverage import CoverageStatus
from app.services.internalization_room.coverage_events import necklaces_of
from app.services.internalization_room.entered import entered
from app.services.internalization_room.live import live
from app.services.internalization_room.session_end import as_utc, end_of
from app.services.internalization_room.takes import READING_ORDER, current_parts
from app.services.internalization_room.team_sessions import beads_of, needs_person
from app.services.project.facilitated_scope import (
    TEAM_NOT_FOUND,
    confined_to,
    readable_project_ids,
)
from app.services.project.reads_project import reads_project

DEFAULT_PAGE = 50
MAX_PAGE = 100


@dataclass(frozen=True)
class _Place:
    at: datetime
    session_id: str


def _encode(place: _Place) -> str:
    raw = f"{place.at.isoformat()}|{place.session_id}".encode()
    return base64.urlsafe_b64encode(raw).decode()


def _decode(cursor: str) -> _Place:
    try:
        at, session_id = base64.urlsafe_b64decode(cursor.encode()).decode().split("|", 1)
        return _Place(at=datetime.fromisoformat(at), session_id=session_id)
    except (ValueError, binascii.Error, UnicodeDecodeError) as broken:
        raise ValidationError("This cursor cannot be read") from broken


def _after(place: _Place) -> ColumnElement[bool]:
    return or_(
        IRSession.updated_at < place.at,
        and_(IRSession.updated_at == place.at, IRSession.id < place.session_id),
    )


async def desk_sessions_page(
    db: AsyncSession,
    user: User,
    *,
    limit: int = DEFAULT_PAGE,
    cursor: str | None = None,
    team_id: str | None = None,
    pericope: str | None = None,
) -> DeskSessionsPage:
    """One page of the readable sessions, narrowed to one team, one passage, or both.

    The two filters are what the Desk's passage picker asks with: a team's sessions of one
    pericope, in either language. A ``team_id`` the reader may not read, or that no team has,
    is the same «Team not found» the inbox answers. The cursor continues inside the narrowed list.
    """
    if team_id is not None:
        if not await reads_project(db, user, team_id):
            raise NotFoundError(TEAM_NOT_FOUND)
        scope = IRSession.project_id == team_id
    else:
        scope = confined_to(IRSession.project_id, await readable_project_ids(db, user))
    page = (
        select(IRSession, Project.name)
        .join(Project, Project.id == IRSession.project_id)
        .where(scope, live(), entered())
    )
    if pericope is not None:
        page = page.where(IRSession.pericope == pericope)
    if cursor is not None:
        page = page.where(_after(_decode(cursor)))

    found = list(
        (
            await db.execute(
                page.order_by(IRSession.updated_at.desc(), IRSession.id.desc()).limit(limit + 1)
            )
        ).tuples()
    )
    more = len(found) > limit
    page_rows = found[:limit]
    names = {session.id: name for session, name in page_rows}
    portraits = await _portraits(db, [session for session, _ in page_rows])
    sessions = [session for session, _ in page_rows if session.id in portraits]

    ids = [session.id for session in sessions]
    rehearsals = await _kept_rehearsals(db, ids)
    released = await _released(db, ids)
    references = {meaning_map.pericope_num: meaning_map.reference for meaning_map in served_maps()}

    return DeskSessionsPage(
        sessions=[
            _item(
                session,
                team_name=names[session.id],
                reference=references.get(session.pericope),
                portrait=portraits[session.id],
                kept_rehearsals=rehearsals.get(session.id, 0),
                has_release=session.id in released,
            )
            for session in sessions
        ],
        next_cursor=(
            _encode(_Place(at=page_rows[-1][0].updated_at, session_id=page_rows[-1][0].id))
            if more and page_rows
            else None
        ),
    )


def _item(
    session: IRSession,
    *,
    team_name: str,
    reference: str | None,
    portrait: dict[str, str],
    kept_rehearsals: int,
    has_release: bool,
) -> DeskSession:
    end = end_of(session)
    beads = beads_of(session, portrait)
    return DeskSession(
        session_id=session.id,
        team_id=str(session.project_id),
        team_name=team_name,
        pericope=session.pericope,
        reference=reference,
        language=session.language,
        state=_state(session, end.state),
        last_activity_at=as_utc(session.updated_at),
        ended_at=end.ended_at,
        attended_at=as_utc(session.attended_at) if session.attended_at is not None else None,
        attended_by=session.attended_by,
        turns=guide_turns_of(session),
        engaged_elements=None
        if beads is None
        else sum(1 for bead in beads if bead.status == CoverageStatus.ENGAGED.value),
        total_elements=None if beads is None else len(beads),
        kept_rehearsals=kept_rehearsals,
        has_release=has_release,
        listener_count=None,
    )


def _state(session: IRSession, state: SessionState) -> DeskSessionState:
    if needs_person(session, state=state):
        return DeskSessionState.NEEDS_PERSON
    if state is SessionState.COMPLETE:
        return DeskSessionState.COMPLETE
    return DeskSessionState.IN_PROGRESS


async def _portraits(db: AsyncSession, sessions: Sequence[IRSession]) -> dict[str, dict[str, str]]:
    passages = {(session.project_id, session.pericope) for session in sessions}
    if not passages:
        return {}
    rows = await db.execute(
        select(IRSession).where(
            tuple_(IRSession.project_id, IRSession.pericope).in_(passages),
            live(),
            entered(),
        )
    )
    return await necklaces_of(db, list(rows.scalars()))


async def _kept_rehearsals(db: AsyncSession, session_ids: list[str]) -> dict[str, int]:
    if not session_ids:
        return {}
    rows = await db.execute(
        select(IRTake)
        .where(
            IRTake.session_id.in_(session_ids),
            IRTake.kind == IRTakeKind.ENSAIO,
            live(IRTake),
        )
        .order_by(*READING_ORDER)
    )
    takes: dict[str, list[IRTake]] = defaultdict(list)
    for take in rows.scalars():
        takes[take.session_id].append(take)
    return {session_id: len(current_parts(held)) for session_id, held in takes.items()}


async def _released(db: AsyncSession, session_ids: list[str]) -> set[str]:
    if not session_ids:
        return set()
    rows = await db.execute(
        select(IRRelease.session_id).where(IRRelease.session_id.in_(session_ids), live(IRRelease))
    )
    return set(rows.scalars())
