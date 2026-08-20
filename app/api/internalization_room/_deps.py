from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access_control import require_app_access
from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import AuthenticationError, ValidationError
from app.db.models.auth import User
from app.services.device.get_device_by_credential import get_device_by_credential

ROOM_KEY_HEADER = "X-Room-Key"
#: What a claimed tablet presents to say which team it belongs to. Read by the header
#: declaration below and by the tests, so the wire name is written once.
DEVICE_CREDENTIAL_HEADER = "X-Device-Credential"
APP_KEY = "internalization-room"

#: The person on the other end of the hand. The team never signs in — a facilitator does,
#: and answering a question is work attributable to someone.
CurrentUser = Annotated[User, require_app_access(APP_KEY)]


async def require_room_key(x_room_key: str | None = Header(default=None)) -> None:
    """Gate the room's endpoints on a shared key.

    The team never signs in — the room is operated by voice and has no keyboard —
    so this is a device key held by the app, not a user credential.
    """
    configured = get_settings().internalization_room_api_key
    if not configured:
        raise ValidationError("INTERNALIZATION_ROOM_API_KEY is not configured")
    if not x_room_key or not secrets.compare_digest(x_room_key, configured):
        raise AuthenticationError(f"Missing or invalid {ROOM_KEY_HEADER} header")


room_key_dep = Depends(require_room_key)


async def require_device(x_room_device: str | None = Header(default=None)) -> str:
    """Which tablet is speaking.

    The room has no accounts, so work is attributed to the device that produced it. The app
    mints this once and keeps it, which is what lets an answer find the team days later and
    what a take is filed under until a team login exists.
    """
    if not x_room_device:
        raise ValidationError("Missing X-Room-Device header")
    return x_room_device


device_dep = Depends(require_device)


async def device_project(
    db: AsyncSession = Depends(get_db),
    x_device_credential: str | None = Header(default=None, alias=DEVICE_CREDENTIAL_HEADER),
) -> str | None:
    """The project of the tablet that is speaking, when it says who it is.

    Optional on purpose, and this is the seam between two slices. The credential is what
    ENG-443 issues at claim, and it is the only device-to-project link there is:
    ``X-Room-Device`` is a string the app mints for itself and matches no row anywhere.

    Requiring it here would lock out every tablet in the field, since the app does not
    send it until ENG-454. So a room that has not been claimed, or that has not shipped
    that half yet, keeps working and its sessions carry no project. Making the credential
    mandatory and retiring ``X-Room-Key`` is ENG-448.
    """
    if not x_device_credential:
        return None

    device = await get_device_by_credential(db, x_device_credential)
    return device.project_id if device else None


device_project_dep = Depends(device_project)
