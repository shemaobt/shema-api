"""The facilitator's own way out of a halt: they went.

`NEEDS_PERSON` had one exit and it belonged to the team — a turn that lands. **The server
still lifts on a landing turn and this slice does not touch that**; `test_the_pause_is_not_a_
latch` is where it is asserted, and an earlier draft of this file claimed the opposite. What
is wrong is that the team's turn was the *only* exit, because it makes the queue drain on the
team's schedule rather than on the facilitator's. A person walks over, helps, and leaves while
the team is still gathering themselves: nothing has landed, so the room is still on the queue
and the tablet is still halted, and the next facilitator to read the queue walks the same walk
again. On a blocking halt the app is also expected to stop sending turns until somebody
restarts it (slice 3), which removes the team's exit in practice as well.

Two routes and not a boolean field on some larger update, so that the undo is as plain as the
mark. The undo matters more than it looks: a mark is a claim about the physical world, and the
person who taps it is the person who will notice, thirty seconds later, that they tapped the
wrong row.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.facilitator._deps import FacilitatorUser
from app.core.database import get_db
from app.db.models.internalization_room import IRSession
from app.models.internalization_room import AttendedResponse
from app.services import internalization_room as room
from app.services.internalization_room import halt
from app.utils.stored_time import as_utc

router = APIRouter()


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
    session_id: str, user: FacilitatorUser, db: AsyncSession = Depends(get_db)
) -> AttendedResponse:
    """A facilitator went to this room: the halt lifts, and who went is recorded.

    Scoped with ``get_session_for_facilitator``, which answers 404 for a session of another
    team exactly as for one that does not exist — this is a write, and the listing that hands
    out these ids is scoped the same way.

    Idempotent, and a room that never halted can be marked all the same; ``attend`` is where
    both of those are argued.
    """
    session = await room.get_session_for_facilitator(db, user, session_id)
    return _answer(await room.attend(db, session, by=user.id))


@router.delete("/facilitator/sessions/{session_id}/attended", response_model=AttendedResponse)
async def undo_attended(
    session_id: str, user: FacilitatorUser, db: AsyncSession = Depends(get_db)
) -> AttendedResponse:
    """Nobody went after all: the stamps clear and the room asks again.

    A session nobody marked answers 200 and changes nothing: there is no claim to withdraw,
    and treating the absence as an error would make an idempotent undo impossible to write on
    the Desk.
    """
    session = await room.get_session_for_facilitator(db, user, session_id)
    return _answer(await room.unattend(db, session))
