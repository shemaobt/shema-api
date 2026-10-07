"""When a stretch becomes a hard stretch, what is kept once it does, and what lands with it.

One rule lives here: the third telling of a stretch marks it, once. The room asks for a person
that one time and never again for that stretch, so a visit already recorded is not erased by
the fourth telling — and the fact itself is written to a table of its own, which nothing that
follows clears. Once is the database's promise now, not a read before the write.

Because the mark belongs to the telling that crossed, the whole of a captured telling is closed
here too: the stretch row, the telling-back state and the mark are one transaction, and both
routes that capture one come through `capture_and_note_a_hard_stretch` to get it.

It sits between the two services rather than inside either: the count is the stretch's and the
halt is the session's, `sessions` already reads `segments`, and `segments` reaching back for
the halt would be a cycle.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRHardStretch, IRSegment, IRSession
from app.services.internalization_room.back_translation import BackTranslationState
from app.services.internalization_room.segments import capture_segment, first_telling_of
from app.services.internalization_room.sessions import (
    RETELLS_BEFORE_A_WARNING,
    raise_a_warning,
    save_back_translation,
)


async def note_a_hard_stretch(db: AsyncSession, session: IRSession, stretch: IRSegment) -> bool:
    """Mark the stretch if it has crossed and carries no mark yet, and say whether this did it.

    **At or past the number, not exactly at it.** Exact equality was the first shape and it was
    brittle in one direction: a crossing that failed after the count moved would have made the
    mark unreachable for that stretch forever, because the count only ever grows. At or past it,
    the next telling finds four and writes what the third could not.

    **The database says who wrote it, not a read before the write.** Two tellings of one stretch
    landing together both read "no mark" and both wrote one, and the second halt cleared
    `attended_at`, `attended_by` and `person_arrived_at` — the record that a facilitator had
    already walked to the room. The unique index refuses the second row; the conflict is
    swallowed and that writer asks for nobody, which is the same answer the fourth telling of a
    marked stretch gets, and by the same mechanism.

    The insert sits **inside** the savepoint, and everything else is flushed **before** the try.
    `begin_nested` flushes whatever is still dirty on the way in, and that flush is emitted
    outside the savepoint: a collision there deactivates the whole transaction rather than
    rolling back to the mark, and caught here it would read as "already marked" and then die at
    the commit. Flushing first leaves only this insert under the `except`.

    The row names the first telling of the chain rather than the version standing now, so the
    consultant reads one name per stretch however many times it was replaced. A telling-back
    started over retires every row and begins a new chain, which can cross and be marked again.

    The row and the halt are one fact and are written in one transaction, and this never closes
    it. Whoever asks for a mark is already writing the telling that earned it — the count on the
    stretch, or the stretch row itself — so the commit belongs to them.
    """
    if stretch.tellings < RETELLS_BEFORE_A_WARNING:
        return False

    first = await first_telling_of(db, stretch)
    await db.flush()
    try:
        async with db.begin_nested():
            db.add(
                IRHardStretch(
                    id=str(uuid.uuid4()),
                    session_id=session.id,
                    segment_id=first.id,
                    tellings=stretch.tellings,
                )
            )
    except IntegrityError:
        return False

    await raise_a_warning(db, session, commit=False)
    return True


async def capture_and_note_a_hard_stretch(
    db: AsyncSession,
    session: IRSession,
    *,
    take_id: str,
    starts_ms: int,
    ends_ms: int,
    bridge_take_id: str | None = None,
    transcript: str | None = None,
    pass_number: int = 1,
    replaces: IRSegment | None = None,
    state: BackTranslationState | None = None,
) -> bool:
    """Write a captured telling and whatever it crossed into, in one transaction.

    The stretch row, the telling-back state and the mark of a hard stretch are one fact about
    one telling. Committed in three, a failure between them left the room in a state nothing
    can reach again: a stretch standing at the number with no mark, in a room that never asked
    for anybody, on a telling the team believes landed.

    `state` is the telling-back state for the routes that carry one; the per-stretch correction
    does not, and passes nothing. It sits here rather than in the router because the router does
    not touch the database (ADR 0009), and here rather than in `segments` because this composes
    the count and the halt, which is what this module is between the two services for.

    The scope a state is stored under is defaulted here for the same reason. Two doors reach
    this capture — the tablet's chunks route and the text seam — and both wrote the default
    themselves, so the rule held until somebody opened a third door.
    """
    captured = await capture_segment(
        db,
        session,
        take_id=take_id,
        starts_ms=starts_ms,
        ends_ms=ends_ms,
        bridge_take_id=bridge_take_id,
        transcript=transcript,
        pass_number=pass_number,
        replaces=replaces,
        commit=False,
    )
    if state is not None:
        state.scope = state.scope or session.pericope
        await save_back_translation(db, session, state, commit=False)
    crossed = await note_a_hard_stretch(db, session, captured)
    await db.commit()
    return crossed


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
