"""Which languages the room claims to speak, and what a caller that names none gets.

The room used to speak one language decided at deploy time. It now speaks the language the
app asks for, and the app asks for whatever the tablet is set to — so this module is the
whole of the room's answer to "which languages exist".

The tuple is written out rather than derived from the authored files. Claiming a language
has to be a deliberate act: derived from the prompts, a language would start being claimed
the moment somebody dropped a half-finished block in, and the guard that fails when a
claimed language is unwritten could never go red.

English is the floor for a caller that names nothing, which is the instinct the authored
fail-safe blocks already have — an unwritten language falls back to the authored English
line, because silence is the one outcome worse than the wrong language.
"""

from __future__ import annotations

from app.core.config import Settings, get_settings

ROOM_LANGUAGES: tuple[str, ...] = ("en", "es", "pt")

FLOOR = "en"

LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "es": "Spanish",
    "pt": "Portuguese",
}


def floor(settings: Settings | None = None) -> str:
    """What a caller that names no language gets, for every caller that has to decide it.

    Read through the setting rather than off ``FLOOR`` directly, because the floor is the one
    knob that has to be movable without a deploy of new code. Holding a fleet on Portuguese
    while an app that names its language is still on its way to the stores is the whole reason
    it exists, and a floor only the synthesizer honoured would have left the sessions and the
    wheel answering English underneath it — which is the failure it is set to prevent.

    Normalized, so a typo in an environment cannot claim a language the room does not speak;
    an unusable value falls back to the constant rather than reaching the room.
    """
    named = (settings or get_settings()).internalization_room_default_language
    return normalize(named) or FLOOR


def normalize(value: str | None) -> str | None:
    """One of the room's languages, or ``None`` for anything it does not speak.

    The region is dropped before the lookup. The room is asked for a locale by an app that
    reads one off a tablet (``pt-BR``, ``es-419``) while everything downstream — the
    authored blocks, the ElevenLabs hint, the language detector — is keyed by the primary
    language, and carrying both forms would be two rows meaning one thing.

    ``None`` in is not the same as an unknown language in: the first is a caller that named
    nothing and takes the floor, the second is a caller that asked for something and must be
    told the room cannot answer it.
    """
    if value is None:
        return None
    primary = value.strip().casefold().split("-")[0]
    return primary if primary in ROOM_LANGUAGES else None
