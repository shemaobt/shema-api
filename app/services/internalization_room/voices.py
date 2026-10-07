"""The voice the room speaks in, by the language it speaks.

The room speaks in Mariana's voice, as Marcia's frozen app does: Portuguese always, and English
too unless a deployment configures an English voice of its own. Which voice is a product
choice made by ear, so it sits in settings and can be corrected without a deploy of new code,
and it is read through here so that every reader agrees on which voices the room has.
"""

from __future__ import annotations

from app.core.config import Settings
from app.core.exceptions import ValidationError


def room_voices(settings: Settings) -> dict[str, str]:
    """Every voice this room may speak in, by the language it speaks.

    An empty English voice means the Portuguese one, decided here so that ``voice_for`` and
    the clip handles agree and an empty value never reaches either.
    """
    return {
        "pt": settings.internalization_room_voice_id,
        "en": settings.internalization_room_voice_id_en or settings.internalization_room_voice_id,
        "es": settings.internalization_room_voice_id_es,
    }


def voice_for(language: str, *, settings: Settings) -> str:
    """The voice for one language.

    Refuses a language the room has no voice for at all. English without a voice of its own is
    not such a language: ``room_voices`` already answers it with the Portuguese voice, which is
    what her app does.

    Does **not** refuse ``es``, on purpose, even though it left ``ROOM_LANGUAGES`` in
    shema-api#362: a session row persisted before that still carries ``language="es"``, and
    refusing it here would 500 that row instead of floor it. The floor is
    ``synthesize_facilitator_speech``'s job, applied before this is ever called — this
    function only ever meets a language the room still claims, or one somebody handed it
    directly without going through the floor, which is theirs to answer for.
    """
    voice = room_voices(settings).get(language)
    if not voice:
        raise ValidationError(f"No voice configured for the room in {language!r}")
    return voice
