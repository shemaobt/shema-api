from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.device import Device


async def touch_device_last_seen(db: AsyncSession, device: Device) -> None:
    """Record that this device just asked the API something.

    The Desk's device list shows last activity, and this is the only place activity can be
    observed: ``GET /api/devices/me`` is the one request a device makes. If the room app
    later gains other calls, they belong here too — otherwise the column quietly means
    "last time it polled" while the screen says "last activity".
    """
    device.last_seen_at = datetime.now(UTC)
    await db.commit()
