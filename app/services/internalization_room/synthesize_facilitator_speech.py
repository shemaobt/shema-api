from __future__ import annotations

import httpx

from app.core.config import Settings, get_settings
from app.services.internalization_room.languages import floor
from app.services.internalization_room.voices import voice_for
from app.services.platform.tts import SpeechStore, SynthesizedSpeech
from app.services.platform.tts import synthesize_speech as platform_speech


async def synthesize_facilitator_speech(
    text: str,
    *,
    language: str | None = None,
    client: httpx.AsyncClient | None = None,
    store: SpeechStore | None = None,
    settings: Settings | None = None,
) -> tuple[SynthesizedSpeech, bool]:
    """Speak one facilitator line in the internalization room's own voice.

    The language is the caller's, because it is the session's, because it is the tablet's.
    A caller that names none gets the floor. The voice follows the language rather than being
    chosen alongside it: the app never picks how the facilitator sounds, only which language
    it sounds in.

    That the voice moves with the language is also what keeps the cache honest. The bucket
    key is content-addressed over text, voice, model, format and tuning but not language, so
    one voice speaking two languages would serve the first language's bytes for the second's
    request. A voice per language puts the language in the key without changing its shape,
    and every clip already bought stays addressable.

    The model is pinned here rather than shared with the rest of the platform because only
    the turbo and flash families honour `language_code`; `eleven_multilingual_v2` detects
    the language from the text, which lets an English word from the map drag a whole
    sentence out of Portuguese.

    The room carries its own ElevenLabs key so its spend and its rate limit are separable
    from the rest of the platform's; an empty setting falls back to the shared one, which
    is what keeps every other caller unchanged.

    Synthesis goes through the platform service, whose cache lives in the bucket: a line
    is paid for once and then answers every replica and every deploy. The in-process LRU
    this used to call started cold on each worker, so a room that failed over mid-session
    paid ElevenLabs again for a sentence it had just spoken.
    """
    cfg = settings or get_settings()
    spoken = language or floor(cfg)
    speech = await platform_speech(
        text,
        language=spoken,
        voice_id=voice_for(spoken, settings=cfg),
        model=cfg.internalization_room_tts_model,
        voice_settings={
            "stability": cfg.internalization_room_voice_stability,
            "similarity_boost": cfg.internalization_room_voice_similarity,
            "style": cfg.internalization_room_voice_style,
            "use_speaker_boost": True,
            "speed": cfg.internalization_room_voice_speed,
        },
        api_key=cfg.internalization_room_elevenlabs_api_key or None,
        settings=cfg,
        client=client,
        store=store,
    )
    return speech, speech.cached
