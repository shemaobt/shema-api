from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.auth import User
from app.db.models.device import Device
from app.services.project.can_access_project import can_access_project

DEVICE_NOT_FOUND = "Device not found"


async def get_team_device(db: AsyncSession, *, user: User, device_id: str) -> Device:
    """A linked device the caller may act on, or ``NotFoundError``.

    Four different situations raise the same error with the same message: the device does
    not exist, it belongs to a team the caller does not facilitate, it belongs to no team
    at all, or it has already been unlinked. That is deliberate and it is the same rule
    ENG-443 holds at the claim — telling "not yours" apart from "no such thing" lets a
    facilitator map an installation by asking about ids.

    Not-found rather than forbidden for the same reason: a 403 would confirm the row is
    real.
    """
    device = (await db.execute(select(Device).where(Device.id == device_id))).scalar_one_or_none()

    if device is None or device.project_id is None or device.unlinked_at is not None:
        raise NotFoundError(DEVICE_NOT_FOUND)
    if not await can_access_project(db, user.id, device.project_id):
        raise NotFoundError(DEVICE_NOT_FOUND)
    return device
