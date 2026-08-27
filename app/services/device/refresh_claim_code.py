from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.db.models.device import Device
from app.services.device import claim_code as claim_codes

_REDRAW_ATTEMPTS = 5


async def refresh_claim_code(db: AsyncSession, device: Device) -> str:
    """Draw a new code for a device whose old one ran out, and return it once.

    A claim code lives fifteen minutes and a tablet can sit on a table for a whole
    afternoon before a facilitator walks past it, so the tablet has to be able to replace
    a dead code without anybody touching it. Minting a whole new device each time would
    work and would leave one abandoned row behind every quarter of an hour.

    Uniqueness, collision and savepoint discipline are ``create_device``'s, for the same
    reasons: the unique index on ``claim_code_hash`` is the guarantee and the redraw is
    the recovery, and undoing a failed draw must not expire every object the session is
    already holding.

    Only for a device nobody has claimed. A spent code is history the row keeps, and
    drawing over it would hand a second facilitator a way to claim a tablet that is
    already someone's.
    """
    for _ in range(_REDRAW_ATTEMPTS):
        code = claim_codes.generate_claim_code()
        device.claim_code_hash = claim_codes.hash_claim_code(code)
        device.claim_code_expires_at = claim_codes.utcnow() + claim_codes.CLAIM_CODE_TTL
        try:
            async with db.begin_nested():
                await db.flush()
        except IntegrityError:
            continue
        await db.commit()
        await db.refresh(device)
        return code

    raise ConflictError("Could not mint a unique claim code.")
