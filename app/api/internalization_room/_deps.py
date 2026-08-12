from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Depends, Header

from app.core.access_control import require_app_access
from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, ValidationError
from app.db.models.auth import User

ROOM_KEY_HEADER = "X-Room-Key"
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
