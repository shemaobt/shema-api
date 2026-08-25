from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.device import Device
from app.services.device.get_device import get_device


async def set_device_label(db: AsyncSession, device_id: str, label: str | None) -> Device:
    """Set or clear the label a facilitator uses to tell two tablets apart.

    The label authenticates nothing and nothing reads it to make a decision, which is why
    it can be changed at any point in a device's life, before or after its code is spent.
    Pass None to clear it.
    """
    device = await get_device(db, device_id)
    if device is None:
        raise NotFoundError("Device not found")

    device.label = label
    await db.commit()
    await db.refresh(device)
    return device
