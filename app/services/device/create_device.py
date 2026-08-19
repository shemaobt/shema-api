from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.db.models.device import Device
from app.models.device import MintedDevice
from app.services.device import claim_code as claim_codes

_MINT_ATTEMPTS = 5


async def create_device(db: AsyncSession, *, label: str | None = None) -> MintedDevice:
    """Create a device with a fresh claim code and no project.

    Uniqueness of the code is held by the unique index on ``devices.claim_code_hash``,
    not by hoping: a draw that collides with a live code is refused by the database and
    redrawn. The constraint is the guarantee and the retry is the recovery — a retry
    alone would be a race between two concurrent mints, and a constraint alone would
    surface a one-in-six-billion collision to a facilitator as an error.

    The redraw happens inside a savepoint so that undoing it undoes only the failed
    insert. Rolling the whole session back would expire every object already loaded in
    it, including a device some earlier call is still holding.
    """
    for _ in range(_MINT_ATTEMPTS):
        code = claim_codes.generate_claim_code()
        device = Device(
            label=label,
            claim_code_hash=claim_codes.hash_claim_code(code),
            claim_code_expires_at=claim_codes.utcnow() + claim_codes.CLAIM_CODE_TTL,
        )
        try:
            async with db.begin_nested():
                db.add(device)
                await db.flush()
        except IntegrityError:
            continue
        await db.commit()
        await db.refresh(device)
        return MintedDevice(device=device, claim_code=code)

    raise ConflictError("Could not mint a unique claim code.")
