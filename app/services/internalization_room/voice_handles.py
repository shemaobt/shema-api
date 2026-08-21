from __future__ import annotations

import base64
import binascii

from app.core.config import Settings

_PREFIX = "tts/"
_QUESTIONS_PREFIX = "internalization-room/questions/"
ROUTE = "/api/internalization-room/voice"
TEAM_AUDIO_ROUTE = "/api/internalization-room/questions/audio"
FACILITATOR_AUDIO_ROUTE = "/api/internalization-room/facilitator/questions/audio"


def to_handle(key: str) -> str:
    """Turn a bucket key into one opaque URL segment.

    The app is handed a handle and hands it straight back; it never learns the voice, the
    model or the tuning behind a line. Encoding also keeps the key's slashes out of the
    path, so the route stays a single segment.
    """
    return base64.urlsafe_b64encode(key.encode("utf-8")).decode("ascii").rstrip("=")


def _decode(handle: str) -> str | None:
    padding = "=" * (-len(handle) % 4)
    try:
        return base64.urlsafe_b64decode(handle + padding).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return None


def from_handle(handle: str, *, settings: Settings) -> str | None:
    """Recover the key, or None when the handle does not address this room's voice.

    A handle is a key in disguise, so it is an instruction from the client about which
    object to read. It is checked against the room's own voice rather than trusted: the
    bucket holds every app's speech, and nothing else in it is this route's business.
    """
    key = _decode(handle)
    if key is None:
        return None
    expected = f"{_PREFIX}{settings.internalization_room_voice_id}/"
    if not key.startswith(expected) or ".." in key:
        return None
    return key


def from_question_handle(handle: str) -> str | None:
    """Recover the key, or None when the handle does not address a question's own audio.

    The same instruction-from-the-client rule as the voice route, narrowed to the one
    folder this feature writes: a team's recording and the facilitator's spoken reply.
    Nothing else in the bucket — no other app's speech, no other app's uploads — is
    reachable by handing these routes a handle for it.
    """
    key = _decode(handle)
    if key is None:
        return None
    if not key.startswith(_QUESTIONS_PREFIX) or ".." in key:
        return None
    return key


def clip_url(key: str) -> str:
    """The address a turn hands the app for the line it must speak."""
    return f"{ROUTE}/{to_handle(key)}"


def team_audio_url(key: str) -> str:
    """The address the app is handed for a facilitator's spoken reply.

    Served by the device-key route, because the team never signs in.
    """
    return f"{TEAM_AUDIO_ROUTE}/{to_handle(key)}" if key else ""


def facilitator_audio_url(key: str) -> str:
    """The address the facilitator's app is handed for a team's recorded question.

    Served by the signed-in route, because a facilitator holds no device key.
    """
    return f"{FACILITATOR_AUDIO_ROUTE}/{to_handle(key)}" if key else ""
