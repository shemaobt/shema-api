from __future__ import annotations

import base64
import binascii

from app.core.config import Settings

_PREFIX = "tts/"

#: Where a team's question and a facilitator's spoken reply are kept. Not synthesized
#: speech, but the same room's audio and served by the same route — which is what the
#: reply's own address already claimed, while the check below refused it.
_QUESTIONS = "internalization-room/questions/"
ROUTE = "/api/internalization-room/voice"


def to_handle(key: str) -> str:
    """Turn a bucket key into one opaque URL segment.

    The app is handed a handle and hands it straight back; it never learns the voice, the
    model or the tuning behind a line. Encoding also keeps the key's slashes out of the
    path, so the route stays a single segment.
    """
    return base64.urlsafe_b64encode(key.encode("utf-8")).decode("ascii").rstrip("=")


def from_handle(handle: str, *, settings: Settings) -> str | None:
    """Recover the key, or None when the handle does not address this room's audio.

    A handle is a key in disguise, so it is an instruction from the client about which
    object to read. It is checked against what belongs to this room rather than trusted:
    the bucket holds every app's speech, and nothing else in it is this route's business.

    Two prefixes belong to the room. `audio_url` has always minted addresses on this route
    for a facilitator's spoken reply, and this check accepted only the first — so every
    reply 404ed by construction, the app never marked one as heard, and the hand went on
    offering the same silent answer forever.
    """
    padding = "=" * (-len(handle) % 4)
    try:
        key = base64.urlsafe_b64decode(handle + padding).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return None
    if ".." in key:
        return None
    voice = f"{_PREFIX}{settings.internalization_room_voice_id}/"
    if not key.startswith(voice) and not key.startswith(_QUESTIONS):
        return None
    return key


def clip_url(key: str) -> str:
    """The address a turn hands the app for the line it must speak."""
    return f"{ROUTE}/{to_handle(key)}"


def audio_url(key: str) -> str:
    """The address for a stored clip that is not synthesized speech — a team's question,
    or a facilitator's spoken reply."""
    return f"{ROUTE}/{to_handle(key)}" if key else ""
