from __future__ import annotations

import base64
import binascii

from app.core.config import Settings

_PREFIX = "tts/"
ROUTE = "/api/internalization-room/voice"


def to_handle(key: str) -> str:
    """Turn a bucket key into one opaque URL segment.

    The app is handed a handle and hands it straight back; it never learns the voice, the
    model or the tuning behind a line. Encoding also keeps the key's slashes out of the
    path, so the route stays a single segment.
    """
    return base64.urlsafe_b64encode(key.encode("utf-8")).decode("ascii").rstrip("=")


def from_handle(handle: str, *, settings: Settings) -> str | None:
    """Recover the key, or None when the handle does not address this room's voice.

    A handle is a key in disguise, so it is an instruction from the client about which
    object to read. It is checked against the room's own voice rather than trusted: the
    bucket holds every app's speech, and nothing else in it is this route's business.
    """
    padding = "=" * (-len(handle) % 4)
    try:
        key = base64.urlsafe_b64decode(handle + padding).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return None
    expected = f"{_PREFIX}{settings.internalization_room_voice_id}/"
    if not key.startswith(expected) or ".." in key:
        return None
    return key


def clip_url(key: str) -> str:
    """The address a turn hands the app for the line it must speak."""
    return f"{ROUTE}/{to_handle(key)}"


def audio_url(key: str) -> str:
    """The address for a stored clip that is not synthesized speech — a team's question,
    or a facilitator's spoken reply."""
    return f"{ROUTE}/{to_handle(key)}" if key else ""
