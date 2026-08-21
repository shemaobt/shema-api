from __future__ import annotations

import secrets

from fastapi import Depends, Header

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, ValidationError

ROOM_KEY_HEADER = "X-Room-Key"


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
