from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.device import RoomDeviceLinkResponse
from app.services.device.get_device import get_device


async def link_for_room_device(db: AsyncSession, device_id: str) -> RoomDeviceLinkResponse | None:
    """The team a tablet belongs to, or None while it belongs to nobody.

    None is the answer for the whole stretch a tablet spends showing a code, so it is the
    common case and not a failure. A device taken out of service reads the same way: the
    row keeps its project, and answering with it would tell a revoked tablet it is still
    somebody's.
    """
    device = await get_device(db, device_id)
    if device is None:
        raise NotFoundError("No device with that id.")
    if device.claimed_at is None or device.unlinked_at is not None or device.project_id is None:
        return None
    return RoomDeviceLinkResponse(project_id=device.project_id, label=device.label)
