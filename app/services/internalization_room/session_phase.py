"""What a session's **Phase** is read from, for as many sessions as a screen asks about.

The facts cost three statements for the whole set and none for an empty one. The rule itself is
``phase_reached``: the session listing and the team reads both come through here to it.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Collection
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import CanonNotKept
from app.db.models.internalization_room import (
    IRRelease,
    IRSegment,
    IRSession,
    IRTake,
    IRTakeKind,
)
from app.models.internalization_room import MomentView
from app.models.internalization_room_desk_sessions import Phase
from app.services.internalization_room.canon.kept import reading_the_canon_of
from app.services.internalization_room.live import live
from app.services.internalization_room.moment import moment_view, phase_reached
from app.services.internalization_room.sessions import back_translation_of, is_panorama
from app.services.internalization_room.takes import READING_ORDER, current_parts
from app.services.internalization_room.turn.scene_view import current_scene_id


@dataclass(frozen=True)
class PhaseFacts:
    kept_rehearsals: dict[str, int]
    released: set[str]
    told: set[str]


async def phases_of(db: AsyncSession, session_ids: Collection[str]) -> dict[str, Phase]:
    """The Phase of each named session: one statement for the rows, then their facts."""
    if not session_ids:
        return {}
    rows = await db.execute(select(IRSession).where(IRSession.id.in_(session_ids)))
    facts = await phase_facts(db, session_ids)
    return {
        session.id: phase_from(session, facts, moment=where_the_room_is(session)[1])
        for session in rows.scalars()
    }


async def phase_facts(db: AsyncSession, session_ids: Collection[str]) -> PhaseFacts:
    return PhaseFacts(
        kept_rehearsals=await _kept_rehearsals(db, session_ids),
        released=await _released(db, session_ids),
        told=await _with_a_told_stretch(db, session_ids),
    )


def phase_from(session: IRSession, facts: PhaseFacts, *, moment: MomentView | None) -> Phase:
    return phase_reached(
        checked_at=back_translation_of(session).checked_at,
        has_release=session.id in facts.released,
        has_told_stretch=session.id in facts.told,
        kept_rehearsals=facts.kept_rehearsals.get(session.id, 0),
        moment=moment,
    )


def where_the_room_is(session: IRSession) -> tuple[str | None, MomentView | None]:
    if is_panorama(session.pericope):
        return None, None
    try:
        with reading_the_canon_of(session.canon_pin):
            scene = current_scene_id(
                session.coverage_state or {}, session.pericope, session.messages or []
            )
            return scene, moment_view(session)
    except CanonNotKept:
        return None, None


async def _kept_rehearsals(db: AsyncSession, session_ids: Collection[str]) -> dict[str, int]:
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


async def _released(db: AsyncSession, session_ids: Collection[str]) -> set[str]:
    if not session_ids:
        return set()
    rows = await db.execute(
        select(IRRelease.session_id).where(IRRelease.session_id.in_(session_ids), live(IRRelease))
    )
    return set(rows.scalars())


async def _with_a_told_stretch(db: AsyncSession, session_ids: Collection[str]) -> set[str]:
    if not session_ids:
        return set()
    rows = await db.execute(
        select(IRSegment.session_id).where(
            IRSegment.session_id.in_(session_ids),
            live(IRSegment),
            IRSegment.superseded_at.is_(None),
            IRSegment.transcript != "",
        )
    )
    return set(rows.scalars())
