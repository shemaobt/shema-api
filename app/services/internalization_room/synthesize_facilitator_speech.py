from __future__ import annotations

from collections import OrderedDict
from collections.abc import Awaitable, Callable
from functools import partial
from typing import TypeVar

import httpx

from app.core.config import Settings, get_settings
from app.services.internalization_room.languages import floor, normalize
from app.services.internalization_room.speakable import speakable_text
from app.services.internalization_room.voices import room_voices, voice_for
from app.services.platform.tts import (
    SpeechKey,
    SpeechStore,
    SynthesizedSpeech,
    Upload,
    synthesize_speech,
    synthesize_speech_key,
)

T = TypeVar("T")

_VOICED_HERE: OrderedDict[str, None] = OrderedDict()
_VOICED_HERE_KEPT = 1024


def voiced_here(key: str) -> bool:
    return key in _VOICED_HERE


async def synthesize_facilitator_speech(
    text: str,
    *,
    language: str | None = None,
    client: httpx.AsyncClient | None = None,
    store: SpeechStore | None = None,
    settings: Settings | None = None,
    uploads: list[Upload] | None = None,
) -> tuple[SpeechKey, bool]:
    """Speak one facilitator line in the internalization room's own voice.

    The language is the caller's, because it is the session's, because it is the tablet's.
    A caller that names none gets the floor, and so does a caller that names a language the
    room no longer claims: `es` left `ROOM_LANGUAGES` in shema-api#362, and a session row
    persisted before that still passes it here on every turn, so a caller is floored before
    the voice is chosen, not after. The voice follows the language rather
    than being chosen alongside it: the app never picks how the facilitator sounds, only
    which language it sounds in.

    ElevenLabs is asked exactly what Marcia's frozen app asks it: the text and the model,
    with no tuning and no language hint, so the voice reads at its own defaults. The bucket
    key is content-addressed over text, voice, model and format but not language, and that is
    right here: while English has no voice of its own, the same text in Portuguese and in
    English is sent the same request, so the same bytes answer both.

    The model is pinned here rather than shared with the rest of the platform because it is
    the one her app speaks with.

    The room carries its own ElevenLabs key so its spend and its rate limit are separable
    from the rest of the platform's; an empty setting falls back to the shared one, which
    is what keeps every other caller unchanged.

    Synthesis goes through the platform service, whose cache lives in the bucket: a line
    is paid for once and then answers every replica and every deploy. The in-process LRU
    this used to call started cold on each worker, so a room that failed over mid-session
    paid ElevenLabs again for a sentence it had just spoken.
    """
    speak = _in_the_rooms_voice(synthesize_speech_key, text, language=language, settings=settings)
    speech = await speak(client=client, store=store, uploads=uploads)
    _VOICED_HERE[speech.key] = None
    _VOICED_HERE.move_to_end(speech.key)
    if len(_VOICED_HERE) > _VOICED_HERE_KEPT:
        _VOICED_HERE.popitem(last=False)
    return speech, speech.cached


async def in_a_voice_the_room_has(key: str, text: str, *, language: str | None) -> str:
    """A clip the room stored earlier, as a key in a voice the room still speaks in.

    A clip handed back from a row — a verdict the team presses `terminei` to hear again, an
    opening prepared ahead — was minted under the voice of its day. The voice route serves
    only the voices the room has now, so a clip minted under a voice it has since dropped
    would answer 404, and every reply the team hears is meant to be in the room's voice. Such a
    clip is voiced again from its words, bought once and cached like any other line; one the
    room can still serve is handed back untouched.
    """
    prefix, _, rest = key.partition("/")
    if prefix != "tts" or rest.split("/", 1)[0] in room_voices(get_settings()).values():
        return key
    speech, _ = await synthesize_facilitator_speech(text, language=language)
    return speech.key


async def render_facilitator_speech(
    text: str, *, language: str, store: SpeechStore
) -> SynthesizedSpeech:
    speak = _in_the_rooms_voice(synthesize_speech, text, language=language, settings=None)
    return await speak(store=store)


def _in_the_rooms_voice(
    speak: Callable[..., Awaitable[T]],
    text: str,
    *,
    language: str | None,
    settings: Settings | None,
) -> Callable[..., Awaitable[T]]:
    cfg = settings or get_settings()
    spoken = normalize(language) or floor(cfg)
    return partial(
        speak,
        speakable_text(text, spoken),
        language=spoken,
        voice_id=voice_for(spoken, settings=cfg),
        model=cfg.internalization_room_tts_model,
        states_language=False,
        api_key=cfg.internalization_room_elevenlabs_api_key or None,
        settings=cfg,
    )
