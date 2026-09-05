"""A tablet with no session says it needs a person, and stops saying it when the room goes.

The only escalation this system had was ``POST /sessions/{id}/needs-person``, addressed by
a session id. That is the right door while there is a session behind it, and the case this
module exists for is the one where there is not: the server has forgotten the session, or
the build broke before one was opened. The tablet is the thing that is still there, so the
halt is recorded on it.

**Recorded once, and the guard is the write.** A tablet on a room's network retries, and a
retry that restamped the moment would tell the facilitator the room stopped just now, every
time — the queue would never age and the oldest halt would never be at the top. So the
``UPDATE`` carries ``WHERE needs_person_since IS NULL`` and the moment answered is the one
read back off the row. Two first calls racing end the same way: one records, the other
reads it. ``collect_device_credential`` guards its own write like this and for the same
reason — the suite runs on SQLite, where ``SELECT ... FOR UPDATE`` is a no-op and a lock
would leave the race untested exactly where the defect lives.

**A device with no team is refused rather than recorded.** The halt is read by the
facilitators of the device's team, so one on a device nobody claimed, or one taken out of
service, is a call for help addressed to nobody. Refusing it is what keeps "recorded" and
"someone will see this" the same sentence.

**It lifts on the room going again, not on a clock and not on a facilitator.** The lift is
called when that device opens a session, which is the shape a session's ``NEEDS_PERSON``
already has: it ends when a turn lands, because the room moving is the evidence that the
halt is over. A facilitator marking it attended from the Desk is a different event —
somebody came — and is still nobody's, which is why nothing here does it. ENG-609's API
slice gave that lift to the *session* halts and deliberately left this half alone, so the
device queue still drains only by the tablet coming back.
"""

from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.db.models.device import Device
from app.services.device.get_device import get_device
from app.services.project.facilitated_scope import confined_to

NOT_LINKED = "This device is not linked to a team."


async def record_needs_person(db: AsyncSession, device_id: str) -> datetime:
    """Record that ``device_id`` needs a person, and return the moment it first said so.

    Raises ``NotFoundError`` for an id this server never minted and ``ConflictError`` while
    the device belongs to no team — never claimed, or taken out of service — because a halt
    on such a device reaches nobody.

    Idempotent while the halt stands: a second call answers the moment of the first. The
    guard is on the write rather than on the read above it, so a retry arriving beside the
    original cannot move the moment either. A halt that is not standing after the write is
    one this call lost to an unlink, and it is refused rather than reported.
    """
    device = await get_device(db, device_id)
    if device is None:
        raise NotFoundError("No device with that id.")
    if device.claimed_at is None or device.unlinked_at is not None:
        raise ConflictError(NOT_LINKED)

    await db.execute(
        update(Device)
        .where(
            Device.id == device.id,
            Device.claimed_at.is_not(None),
            Device.unlinked_at.is_(None),
            Device.needs_person_since.is_(None),
        )
        .values(needs_person_since=datetime.now(UTC))
    )
    await db.commit()
    await db.refresh(device)

    if device.needs_person_since is None:
        raise ConflictError(NOT_LINKED)

    return device.needs_person_since


async def clear_needs_person(db: AsyncSession, device_id: str) -> None:
    """Lift the halt on ``device_id``, if one stands. Silent when none does.

    Unguarded, unlike the write above: there is one state to reach and reaching it twice is
    reaching it once.
    """
    await db.execute(
        update(Device)
        .where(Device.id == device_id, Device.needs_person_since.is_not(None))
        .values(needs_person_since=None)
    )
    await db.commit()


async def devices_waiting_on_a_person(
    db: AsyncSession, project_ids: list[str] | None
) -> list[Device]:
    """Every halted device among ``project_ids``, newest halt first.

    ``None`` is "every team there is", which is what a platform admin's scope resolves to.
    Spelled through ``confined_to`` rather than restated, so this list and the sessions it
    is answered beside are scoped by one sentence.

    Unlinked devices are excluded for the reason ``list_team_devices`` excludes them: the
    row keeps its ``project_id`` after a facilitator takes the tablet out of service, so a
    halt recorded before that would otherwise outlive the device it was recorded on.
    """
    rows = await db.execute(
        select(Device)
        .where(
            Device.needs_person_since.is_not(None),
            Device.unlinked_at.is_(None),
            confined_to(Device.project_id, project_ids),
        )
        .order_by(Device.needs_person_since.desc())
    )
    return list(rows.scalars().all())
