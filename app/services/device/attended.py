"""A facilitator went to a tablet, which lifts its halt, and can say they did not after all.

ENG-624 records a halt on the device — the tablet is the thing that is still there when the
session is not — and gave it a single exit: that tablet opening a session. So the queue
drained on the room's schedule and never on the facilitator's. The person who walked over,
helped, and left while the team was still gathering themselves had nothing to say; the row
stayed at the top of every colleague's queue until the room came back, which may be an hour
later and may be never. ``clear_needs_person``'s own docstring left this lift to nobody. This
is it.

**The lift is recorded as the moment it lifted, not as a flag.** ``needs_person_since`` is
null while the mark stands, so an undo would have nothing left to restore the halt *from* and
would have to stamp it now. The queue is ordered by that moment, newest halt first, and the
age a facilitator reads comes off it — so a tablet that stopped twenty minutes ago would come
back at the head of the list, above rooms that really did stop after it, announcing a halt
that never happened. ``attended_lifted_since`` is that
missing fact, and it is written at the moment of the mark because afterwards there is nothing
left to work it out from.

**A tablet that came back on its own leaves nothing to undo.** Opening a session is the
tablet's own exit and would have lifted the halt with or without the visit, so the lift record
is cleared there (``clear_needs_person``). Without that, a facilitator correcting a tap they
made ten minutes ago would halt a tablet in the middle of a session and send a colleague to a
room that is working — the same defect ``lifted_halt`` closes on the session side.

**Three refusals and two statuses.** An unknown id, a tablet of another team and one no team
ever claimed are one answer, because a facilitator who could tell "not yours" from "no such
thing" could map an installation by asking about ids — the rule ``get_team_device`` holds at
every other device route. A tablet the caller's own team took out of service is the one case
that is safe to name: they already facilitate it, so the refusal tells them nothing they could
not read off their own panel, and what it tells them is true — there is nobody to attend.
"""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.db.models.auth import User
from app.db.models.device import Device
from app.services.device.get_device import get_device
from app.services.project.facilitates_project import facilitates_project

DEVICE_NOT_FOUND = "Device not found"
OUT_OF_SERVICE = "This device has been taken out of service."


async def _device_to_attend(db: AsyncSession, *, user: User, device_id: str) -> Device:
    """The tablet this facilitator may record a visit to, or a refusal saying which kind."""
    device = await get_device(db, device_id)
    if device is None or device.project_id is None:
        raise NotFoundError(DEVICE_NOT_FOUND)
    if not await facilitates_project(db, user, device.project_id):
        raise NotFoundError(DEVICE_NOT_FOUND)
    if device.unlinked_at is not None:
        raise ConflictError(OUT_OF_SERVICE)
    return device


async def attend_device(db: AsyncSession, *, user: User, device_id: str) -> Device:
    """A facilitator says they went to this tablet, which lifts the halt if one stands.

    **Idempotent, keeping the first stamp.** Two taps are one visit, and a stamp that moved on
    every tap would record when somebody last touched the Desk rather than when they went to
    the tablet — and the moment of the visit is the whole of what the field is for.

    A tablet that is not halted is marked all the same and moves nowhere. They went anyway,
    and that is worth recording; there is simply no halt for the mark to lift, which is what
    leaving ``attended_lifted_since`` null says and what makes the undo of such a mark move
    nothing.
    """
    device = await _device_to_attend(db, user=user, device_id=device_id)

    if device.attended_at is None:
        device.attended_at = datetime.now(UTC)
        device.attended_by = user.id
    if device.needs_person_since is not None:
        device.attended_lifted_since = device.needs_person_since
        device.needs_person_since = None

    await db.commit()
    await db.refresh(device)
    return device


async def unattend_device(db: AsyncSession, *, user: User, device_id: str) -> Device:
    """Withdraw the mark: nobody went, so the tablet asks again with the moment it asked.

    What comes back is what this visit lifted and nothing else. A visit that lifted nothing
    undoes to nothing, and a tablet that has opened a session since has had its lift record
    cleared by that session — there is no halt left to restore, because the tablet's own exit
    already happened.

    A tablet nobody marked answers 200 and changes nothing: there is no claim to withdraw, and
    treating the absence as an error would make an idempotent undo impossible to write on the
    Desk.
    """
    device = await _device_to_attend(db, user=user, device_id=device_id)
    if device.attended_at is None:
        return device

    lifted = device.attended_lifted_since
    device.attended_at = None
    device.attended_by = None
    device.attended_lifted_since = None
    if lifted is not None and device.needs_person_since is None:
        device.needs_person_since = lifted

    await db.commit()
    await db.refresh(device)
    return device
