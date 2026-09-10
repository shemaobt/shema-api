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
from app.services.internalization_room.segments import first_telling_of
from app.services.internalization_room.sessions import (
    RETELLS_BEFORE_A_WARNING,
    mark_needs_person,
)


async def note_a_hard_stretch(db: AsyncSession, session: IRSession, stretch: IRSegment) -> bool:
    """Mark the stretch if this telling is the one that crosses, and say whether it did.

    Exactly at the number, never at or past it. Past it is what the room used to do, and it
    made every telling from the third onward a new ask — which cleared `attended_at`,
    `attended_by` and `person_arrived_at` each time, deleting the record that a facilitator had
    already walked over. The stretch crosses once because the count only ever grows by one.

    The row names the first telling of the chain rather than the version standing now, so the
    consultant reads one name per frase however many times it was replaced.
    """
    if stretch.tellings != RETELLS_BEFORE_A_WARNING:
        return False

    first = await first_telling_of(db, stretch)
    db.add(
        IRHardStretch(
            id=str(uuid.uuid4()),
            session_id=session.id,
            segment_id=first.id,
            tellings=stretch.tellings,
        )
    )
    await db.commit()
    await mark_needs_person(db, session, kind=HaltKind.WARNING)
    return True


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
