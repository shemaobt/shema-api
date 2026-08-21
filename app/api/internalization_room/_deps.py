from __future__ import annotations

import secrets

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import AuthenticationError, ValidationError
from app.db.models.device import Device
from app.services.device.authenticate_device import authenticate_device

ROOM_KEY_HEADER = "X-Room-Key"
#: What a claimed tablet presents to say which team it belongs to. Read by the header
#: declaration below and by the tests, so the wire name is written once.
DEVICE_CREDENTIAL_HEADER = "X-Device-Credential"


async def require_room_caller(
    db: AsyncSession = Depends(get_db),
    x_device_credential: str | None = Header(default=None, alias=DEVICE_CREDENTIAL_HEADER),
    x_room_key: str | None = Header(default=None),
) -> Device | None:
    """Who is at the room's door: a device that can name itself, or a holder of the key.

    The team never signs in — the room is operated by voice and has no keyboard — so both
    of these are device credentials, not user credentials. What separates them is how many
    devices each one describes.

    ``X-Device-Credential`` names **one** device row, and through it one project. Revoking
    it is a write to that row and takes effect on the next request. This is what ENG-448
    adds and what every tablet should be presenting.

    ``X-Room-Key`` is one string shipped inside the app bundle, identical in every
    installation. It identifies nobody, and there is nothing to revoke because there is
    nothing that tells two tablets apart.

    **Both are accepted, and that is a dated compromise, not a design.** The room app does
    not hold a credential until ENG-455; refusing the shared key before then would open
    the door for nobody. Retiring it is the other half of ENG-448 and deliberately not in
    this slice — see the pull request for what the date has to wait on.

    A device that presents a credential is judged on it alone. Falling back to the shared
    key after a credential was refused would hand a revoked tablet the same way in that
    every other tablet uses, which is the revocation undone.
    """
    if x_device_credential:
        device = await authenticate_device(db, x_device_credential)
        if device is None:
            raise AuthenticationError("Invalid device credential")
        return device

    configured = get_settings().internalization_room_api_key
    if not configured:
        raise ValidationError("INTERNALIZATION_ROOM_API_KEY is not configured")
    if not x_room_key or not secrets.compare_digest(x_room_key, configured):
        raise AuthenticationError(f"Missing or invalid {ROOM_KEY_HEADER} header")
    return None


room_caller_dep = Depends(require_room_caller)


async def require_device(x_room_device: str | None = Header(default=None)) -> str:
    """Which tablet is speaking.

    The room has no accounts, so work is attributed to the device that produced it. The app
    mints this once and keeps it, which is what lets an answer find the team days later and
    what a take is filed under until a team login exists.

    Self-issued and unauthenticated: it matches no row anywhere, which is why it says which
    tablet but never which project. ``require_room_caller`` is what answers that.
    """
    if not x_room_device:
        raise ValidationError("Missing X-Room-Device header")
    return x_room_device


device_dep = Depends(require_device)


async def device_project(caller: Device | None = Depends(require_room_caller)) -> str | None:
    """The project of the tablet that is speaking, when it says who it is.

    Still optional, and for the same reason the shared key is still accepted: a caller who
    came in on ``X-Room-Key`` has named no device, so there is no project to resolve and
    its sessions carry none. That stops being possible when the key is retired.

    Derived from the gate's own result rather than looked up again — the credential is
    resolved once per request, and FastAPI's dependency cache is what makes the two
    declarations one query.
    """
    return caller.project_id if caller else None


device_project_dep = Depends(device_project)
