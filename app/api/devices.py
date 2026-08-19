"""What a device may ask about itself, authenticated by the credential it was issued.

This is the device's half of "the link reaches the tablet without anyone typing into it":
the app already holds the credential it got at claim time, and this is where it reads which
project that credential belongs to. The app-side polling and display is ENG-454.

Nothing here touches ``X-Room-Key`` or ``X-Room-Device``. Requiring this credential in
place of those is ENG-448, and doing it now would lock out every tablet in the field.
"""

from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AuthenticationError
from app.db.models.device import Device
from app.models.device import DeviceSelfResponse
from app.services.device.get_device_by_credential import get_device_by_credential

devices_router = APIRouter()


async def require_device_credential(
    db: AsyncSession = Depends(get_db),
    x_device_credential: str | None = Header(default=None),
) -> Device:
    """The device behind ``X-Device-Credential``.

    A missing credential and an unrecognised one answer identically. A device that has
    never been claimed holds no credential at all, so it cannot reach past this.
    """
    if not x_device_credential:
        raise AuthenticationError("Invalid device credential")

    device = await get_device_by_credential(db, x_device_credential)
    if device is None:
        raise AuthenticationError("Invalid device credential")
    return device


@devices_router.get("/me", response_model=DeviceSelfResponse)
async def read_own_device(
    device: Device = Depends(require_device_credential),
) -> DeviceSelfResponse:
    """Which project this device belongs to. Never answers with the credential."""
    return DeviceSelfResponse(
        device_id=device.id,
        project_id=device.project_id,
        label=device.label,
    )
