from __future__ import annotations

import secrets

from fastapi import Depends, Header

from app.api.facilitator._deps import FacilitatorUser
from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, ValidationError

ROOM_KEY_HEADER = "X-Room-Key"
APP_KEY = "internalization-room"

#: The person on the other end of the hand. The team never signs in — a facilitator does,
#: and answering a question is work attributable to someone.
#:
#: Bound to the Desk's own gate rather than to a second call of ``require_role``, so the two
#: route families are guarded by one object and the audit can recognise both. Holding *a*
#: role on this app used to be enough here, which let a team's own role open a facilitator's
#: routes.
CurrentUser = FacilitatorUser


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
