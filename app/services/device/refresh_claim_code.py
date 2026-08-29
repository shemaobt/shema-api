from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.db.models.device import Device
from app.services.device import claim_code as claim_codes

_REDRAW_ATTEMPTS = 5


async def refresh_claim_code(db: AsyncSession, device: Device) -> str:
    """Draw a code for a device and return it once — the only place a code is ever drawn.

    A claim code lives fifteen minutes and a tablet can sit on a table for a whole
    afternoon before a facilitator walks past it, so the tablet has to be able to replace
    a dead code without anybody touching it. Minting a whole new device each time would
    work and would leave one abandoned row behind every quarter of an hour.

    It does not ask whether the old code is still alive, and it cannot: the row keeps only
    a hash, so a code that is still good can never be served a second time. A tablet asking
    again — because it was restarted, or because its code ran out — has to be answered with
    a new one either way.

    Uniqueness, collision and savepoint discipline are ``create_device``'s, for the same
    reasons: the unique index on ``claim_code_hash`` is the guarantee and the redraw is
    the recovery, and undoing a failed draw must not expire every object the session is
    already holding.

    The row is written **inside** the savepoint rather than before it, which is the whole
    of the protection here. ``begin_nested`` snapshots the session on the way in, and that
    snapshot flushes whatever is already dirty — so a device mutated a line earlier has its
    UPDATE emitted outside the savepoint, where a collision deactivates the transaction and
    the next attempt raises ``PendingRollbackError`` past ``except IntegrityError`` as a 500.
    ``create_device`` is safe only because its ``db.add`` sits inside the block too.

    Only for a device nobody has claimed. A spent code is history the row keeps, and
    drawing over it would hand a second facilitator a way to claim a tablet that is
    already someone's.

    ``create_device`` draws through here too, passing a device that is not in the session
    yet — which is why the ``add`` is inside the block with everything else.
    """
    for _ in range(_REDRAW_ATTEMPTS):
        code = claim_codes.generate_claim_code()
        try:
            async with db.begin_nested():
                device.claim_code_hash = claim_codes.hash_claim_code(code)
                device.claim_code_expires_at = claim_codes.utcnow() + claim_codes.CLAIM_CODE_TTL
                db.add(device)
                await db.flush()
        except IntegrityError:
            continue
        await db.commit()
        await db.refresh(device)
        return code

    raise ConflictError("Could not mint a unique claim code.")
