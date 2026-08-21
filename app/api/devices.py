"""What a device may ask about itself, authenticated by the credential it was issued.

This is the device's half of "the link reaches the tablet without anyone typing into it":
the app already holds the credential it got at claim time, and this is where it reads which
project that credential belongs to. The app-side polling and display is ENG-454.

Nothing here touches ``X-Room-Key`` or ``X-Room-Device``. The room's own routes accept
this credential as of ENG-448; retiring the shared key beside it is the half of that issue
that waits on the app (ENG-455).

Rotation lives here rather than on a facilitator route because the device is the only party
that must not lose the answer, and it is the one holding the credential that pays for it.
"""

from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AuthenticationError
from app.db.models.device import Device
from app.models.device import DeviceCredentialResponse, DeviceSelfResponse
from app.services.device.authenticate_device import authenticate_device
from app.services.device.rotate_device_credential import rotate_device_credential
from app.services.device.touch_device_last_seen import touch_device_last_seen

devices_router = APIRouter()


async def require_device_credential(
    db: AsyncSession = Depends(get_db),
    x_device_credential: str | None = Header(default=None),
) -> Device:
    """The device behind ``X-Device-Credential``.

    A missing credential and an unrecognised one answer identically. A device that has
    never been claimed holds no credential at all, so it cannot reach past this.

    A *revoked* one does not: ``authenticate_device`` raises, and the tablet is told it was
    unlinked so it can forget what it holds instead of retrying forever.
    """
    if not x_device_credential:
        raise AuthenticationError("Invalid device credential")

    device = await authenticate_device(db, x_device_credential)
    if device is None:
        raise AuthenticationError("Invalid device credential")
    return device


def _presented(x_device_credential: str | None = Header(default=None)) -> str:
    """The credential as sent, for the one route that has to keep it working."""
    if not x_device_credential:
        raise AuthenticationError("Invalid device credential")
    return x_device_credential


@devices_router.get("/me", response_model=DeviceSelfResponse)
async def read_own_device(
    device: Device = Depends(require_device_credential),
    db: AsyncSession = Depends(get_db),
) -> DeviceSelfResponse:
    """Which project this device belongs to. Never answers with the credential.

    Stamps last-seen on the way through: this is the only request a device makes, so it is
    the only place the Desk's "last activity" column can come from.
    """
    await touch_device_last_seen(db, device)
    return DeviceSelfResponse(
        device_id=device.id,
        project_id=device.project_id,
        label=device.label,
    )


@devices_router.post("/me/credential", response_model=DeviceCredentialResponse)
async def rotate_own_credential(
    device: Device = Depends(require_device_credential),
    presented: str = Depends(_presented),
    db: AsyncSession = Depends(get_db),
) -> DeviceCredentialResponse:
    """Trade the credential this device holds for a fresh one, with no claim and no visit.

    The credential presented keeps working until the returned one is used, so a lost
    response costs a retry rather than the room. See ``rotate_device_credential``.
    """
    issued = await rotate_device_credential(db, device, presented=presented)
    return DeviceCredentialResponse(device_id=device.id, credential=issued)
