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

from sqlalchemy import ColumnElement, and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import SessionState
from app.core.exceptions import ValidationError
from app.db.models.auth import User
from app.db.models.internalization_room import IRRelease, IRSession, IRTake, IRTakeKind
from app.db.models.project import Project
from app.models.internalization_room_desk_sessions import (
    DeskSession,
    DeskSessionsPage,
    DeskSessionState,
)
from app.services.internalization_room.canon.parse_map import ROOM_BOOK, load_book
from app.services.internalization_room.coverage import CoverageStatus
from app.services.internalization_room.coverage_events import necklaces_of
from app.services.internalization_room.entered import entered
from app.services.internalization_room.live import live
from app.services.internalization_room.session_end import as_utc, end_of
from app.services.internalization_room.takes import current_parts
from app.services.internalization_room.team_sessions import beads_of, needs_person
from app.services.project.facilitated_scope import confined_to, facilitated_project_ids

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
    db: AsyncSession, user: User, *, limit: int = DEFAULT_PAGE, cursor: str | None = None
) -> DeskSessionsPage:
    page = (
        select(IRSession, Project.name)
        .join(Project, Project.id == IRSession.project_id)
        .where(
            confined_to(IRSession.project_id, await facilitated_project_ids(db, user)),
            live(),
            entered(),
        )
    )
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
    names = {session.id: name for session, name in found[:limit]}
    sessions = [session for session, _ in found[:limit]]

    ids = [session.id for session in sessions]
    portraits = await _portraits(db, sessions)
    rehearsals = await _kept_rehearsals(db, ids)
    released = await _released(db, ids)
    references = {
        meaning_map.pericope_num: meaning_map.reference for meaning_map in load_book(ROOM_BOOK)
    }

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
            _encode(_Place(at=sessions[-1].updated_at, session_id=sessions[-1].id))
            if more and sessions
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
        turns=sum(1 for line in session.messages or [] if line.get("role") == "guide"),
        engaged_elements=sum(1 for bead in beads if bead.status == CoverageStatus.ENGAGED.value),
        total_elements=len(beads),
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
            IRSession.project_id.in_({team for team, _ in passages}),
            IRSession.pericope.in_({pericope for _, pericope in passages}),
            live(),
            entered(),
        )
    )
    by_team: dict[str | None, list[IRSession]] = defaultdict(list)
    for session in rows.scalars():
        if (session.project_id, session.pericope) in passages:
            by_team[session.project_id].append(session)

    portraits: dict[str, dict[str, str]] = {}
    for conversations in by_team.values():
        portraits.update(await necklaces_of(db, conversations))
    return portraits


async def _kept_rehearsals(db: AsyncSession, session_ids: list[str]) -> dict[str, int]:
    if not session_ids:
        return {}
    rows = await db.execute(
        select(IRTake)
        .where(IRTake.session_id.in_(session_ids), IRTake.kind == IRTakeKind.ENSAIO)
        .order_by(
            IRTake.ordinal.asc().nulls_first(),
            IRTake.pass_number.asc().nulls_first(),
            IRTake.created_at,
        )
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
