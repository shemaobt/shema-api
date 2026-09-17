from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.device import Device
from app.models.device import MintedDevice
from app.services.device.refresh_claim_code import refresh_claim_code


async def create_device(db: AsyncSession, *, label: str | None = None) -> MintedDevice:
    """Create a device with a fresh claim code and no project.

    The draw itself — uniqueness by index rather than by hope, the redraw on collision, and
    the savepoint that keeps a failed insert from expiring every object the session is
    holding — is ``refresh_claim_code``'s, and is the same act whether the row is new or is
    showing a code that ran out. It lived here in a second copy until the two drifted: one
    of them wrote the row outside the savepoint, so its retry could never retry.
    """
    return MintedDevice(
        device=(device := Device(label=label)),
        claim_code=await refresh_claim_code(db, device),
    )
