"""The room's voice, one per language it speaks.

``app/services/platform/voices.py`` makes the argument this module obeys: a voice "retains
its unique characteristics *and accent* in any language it speaks", so one multilingual
voice reading three languages sounds like a Brazilian reading English. The room's own key
and tuning are separable from the platform's, so it keeps its own map rather than borrowing
that one.

Which voice belongs to which language is a product choice made by ear. It sits in settings
so a bad match can be corrected without a deploy of new code, and it is read through here so
that adding a language is one entry rather than a search for every place a voice is named.
"""

from __future__ import annotations

from app.core.config import Settings
from app.services.internalization_room.languages import FLOOR


def room_voices(settings: Settings) -> dict[str, str]:
    """Every voice this room may speak in, by the language it speaks."""
    return {
        "pt": settings.internalization_room_voice_id,
        "en": settings.internalization_room_voice_id_en,
    }


def voice_for(language: str, *, settings: Settings) -> str:
    """The voice for one language, falling back to the floor's rather than to silence."""
    voices = room_voices(settings)
    return voices.get(language) or voices[FLOOR]
