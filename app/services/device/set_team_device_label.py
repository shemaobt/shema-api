from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.device import Device
from app.services.device.get_team_device import get_team_device


async def set_team_device_label(
    db: AsyncSession, *, user: User, device_id: str, label: str
) -> Device:
    """Say who uses a device. Devices change hands, so this is ordinary, not exceptional.

    Stored exactly as typed — no trimming, no casing, no shape. It is a note a facilitator
    writes to recognise a tablet on a shelf, it authenticates nothing, and an empty string
    is a legitimate value meaning they no longer want a note there.
    """
    device = await get_team_device(db, user=user, device_id=device_id)
    device.label = label
    await db.commit()
    await db.refresh(device)
    return device
