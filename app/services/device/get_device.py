from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.device import Device


async def get_device(db: AsyncSession, device_id: str) -> Device | None:
    """The device with ``device_id``, or None. A device with no project is normal."""
    return (await db.execute(select(Device).where(Device.id == device_id))).scalar_one_or_none()
