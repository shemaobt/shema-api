"""The facilitator's Visit: they went to a room, and the Desk records it (ADR 0076).

The visit writes nothing on the session's status. It takes a halted room off the queue and is
the only end of a warning; a blocking halt is lifted only by the team's own return.

Two routes and not a boolean field on some larger update, so that the undo is as plain as the
mark. The undo matters more than it looks: a mark is a claim about the physical world, and the
person who taps it is the person who will notice, thirty seconds later, that they tapped the
wrong row.

Both name the halt the Desk read, its halt count and its warning, so a write that lands after
the room halted again is refused rather than answering a halt nobody saw (ADR 0091).
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from pydantic import AwareDatetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.facilitator._deps import FacilitatorUser
from app.core.database import get_db
from app.db.models.internalization_room import IRSession
from app.models.internalization_room import AttendedResponse
from app.services import internalization_room as room
from app.services.internalization_room import halt
from app.services.internalization_room.nudge_channel import nudge
from app.utils.stored_time import as_utc

router = APIRouter()

#: ``halts_raised`` is an ``Integer`` column: a larger count could name no room, and Postgres
#: would refuse to bind it.
HALTS_RAISED_MAX = 2**31 - 1


def _on_the_stored_clock(warning: datetime | None) -> datetime | None:
    """The warning as the instant it is stored at: the Desk may name it on any offset."""
    return warning.astimezone(UTC) if warning is not None else None


def _answer(session: IRSession) -> AttendedResponse:
    return AttendedResponse(
        session_id=session.id,
        status=session.status.value,
        halt=halt.standing(session),
        attended_at=(
            as_utc(session.attended_at).isoformat() if session.attended_at is not None else None
        ),
        attended_by=session.attended_by,
    )


@router.post("/facilitator/sessions/{session_id}/attended", response_model=AttendedResponse)
async def mark_attended(
    session_id: str,
    user: FacilitatorUser,
    halt: int = Query(ge=0, le=HALTS_RAISED_MAX),
    warning: AwareDatetime | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> AttendedResponse:
    """A facilitator went to this room: who went is recorded, and the status is not written.

    Scoped with ``get_session_for_facilitator``, which answers 404 for a session of another
    team exactly as for one that does not exist — this is a write, and the listing that hands
    out these ids is scoped the same way.

    Idempotent, and a room that never halted can be marked all the same; ``attend`` is where
    both of those are argued.

    ``halt`` and ``warning`` are the halt count and the warning the Desk read, no warning when
    absent; another is ``HALT_MOVED``.
    """
    session = await room.get_session_for_facilitator(db, user, session_id)
    attended = await room.attend(
        db, session, by=user.id, halts_raised=halt, warned_at=_on_the_stored_clock(warning)
    )
    nudge(attended.project_id, "halts")
    return _answer(attended)


@router.delete("/facilitator/sessions/{session_id}/attended", response_model=AttendedResponse)
async def undo_attended(
    session_id: str,
    user: FacilitatorUser,
    halt: int = Query(ge=0, le=HALTS_RAISED_MAX),
    warning: AwareDatetime | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> AttendedResponse:
    """Nobody went after all: the stamps clear and a halted room is back on the queue.

    A demo team's halted room is attended again at once, by the server (ADR 0064).

    A session nobody marked answers 200 and changes nothing: there is no claim to withdraw,
    and treating the absence as an error would make an idempotent undo impossible to write on
    the Desk.

    ``halt`` and ``warning`` are the halt count and the warning the Desk read, no warning when
    absent; another is ``HALT_MOVED``.
    """
    session = await room.get_session_for_facilitator(db, user, session_id)
    unattended = await room.unattend(
        db, session, halts_raised=halt, warned_at=_on_the_stored_clock(warning)
    )
    nudge(unattended.project_id, "halts")
    return _answer(unattended)
