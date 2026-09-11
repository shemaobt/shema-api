"""When a stretch becomes a hard stretch, and what is kept once it does.

One rule lives here: the third telling of a stretch marks it, once. The room asks for a person
that one time and never again for that stretch, so a visit already recorded is not erased by
the fourth telling — and the fact itself is written to a table of its own, which nothing that
follows clears.

It sits between the two services rather than inside either: the count is the stretch's and the
halt is the session's, and `sessions` already reads `segments`.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.room_enums import HaltKind
from app.db.models.internalization_room import IRHardStretch, IRSegment, IRSession
from app.services.internalization_room.segments import (
    first_telling_of,
    refuse_a_stretch_that_is_not_a_unit,
)
from app.services.internalization_room.sessions import (
    RETELLS_BEFORE_A_WARNING,
    mark_needs_person,
)


async def note_a_hard_stretch(db: AsyncSession, session: IRSession, stretch: IRSegment) -> bool:
    """Mark the stretch if it has crossed and carries no mark yet, and say whether this did it.

    **At or past the number, and only while the chain has no mark.** Exact equality was the
    first shape and it was brittle in one direction that matters: the captured path writes the
    row in one transaction and the mark in the next, so a failure between them left a stretch
    standing at the number with no mark — and an equality gate then made the mark unreachable
    for that stretch forever, because the count only ever grows. Asking the table instead makes
    the crossing recoverable: the next telling finds four, finds no mark, and writes it.

    It is the mark and not the count that keeps the ask to one. That is what stops the fourth
    telling clearing `attended_at`, `attended_by` and `person_arrived_at`, which is the record
    that a facilitator already walked over.

    The row names the first telling of the chain rather than the version standing now, so the
    consultant reads one name per stretch however many times it was replaced. A telling-back
    started over retires every row and begins a new chain, which can cross and be marked again.

    The row and the halt are written in one transaction — `mark_needs_person` is what commits —
    because they are one fact. Committed apart, a failure between them leaves a stretch marked
    hard in a room that never asked for anybody.
    """
    if stretch.tellings < RETELLS_BEFORE_A_WARNING:
        return False

    first = await first_telling_of(db, stretch)
    if await _already_marked(db, session.id, first.id):
        return False

    db.add(
        IRHardStretch(
            id=str(uuid.uuid4()),
            session_id=session.id,
            segment_id=first.id,
            tellings=stretch.tellings,
        )
    )
    await mark_needs_person(db, session, kind=HaltKind.WARNING)
    return True


async def count_an_empty_telling(db: AsyncSession, session: IRSession, stretch: IRSegment) -> bool:
    """Count a telling nobody could make out, and mark the stretch if that crossed it.

    Nothing is captured, so there is no new row to carry the count onto: it goes on the row
    that is standing. Not counting it is what made the room unreachable exactly when it was
    broken — during a transcriber outage every attempt comes back empty, and the team could
    tell one stretch forever without the room ever offering them a person.

    The count and the mark land in **one** transaction. Committed apart, a failure between them
    left the count at the number with no mark, which is a stretch the room can never ask about
    again on the reading `mark_needs_person` gives it.

    A row that no longer counts, or one the team divided, is refused before anything is counted
    on it — the same answer the captured path gets from `capture_segment`. Unguarded, a tablet
    retrying a correction it already sent spent a telling on a stretch the room had retired, and
    a divided parent could be marked hard although nothing can ever replace it.
    """
    await refuse_a_stretch_that_is_not_a_unit(db, session.id, stretch)
    stretch.tellings += 1
    await db.flush()
    crossed = await note_a_hard_stretch(db, session, stretch)
    if not crossed:
        await db.commit()
    await db.refresh(stretch)
    return crossed


async def _already_marked(db: AsyncSession, session_id: str, segment_id: str) -> bool:
    result = await db.execute(
        select(IRHardStretch.id).where(
            IRHardStretch.session_id == session_id,
            IRHardStretch.segment_id == segment_id,
        )
    )
    return result.first() is not None


async def hard_stretches_of(
    db: AsyncSession, session_ids: list[str]
) -> dict[str, list[IRHardStretch]]:
    """The marks of many sessions at once, keyed by session.

    One query for the whole queue rather than one per row: the facilitator's list is the one
    read that crosses teams, and a query per row is how it stops being a list.
    """
    if not session_ids:
        return {}
    result = await db.execute(
        select(IRHardStretch)
        .where(IRHardStretch.session_id.in_(session_ids))
        .order_by(IRHardStretch.crossed_at, IRHardStretch.segment_id)
    )
    marks: dict[str, list[IRHardStretch]] = {}
    for mark in result.scalars():
        marks.setdefault(mark.session_id, []).append(mark)
    return marks
