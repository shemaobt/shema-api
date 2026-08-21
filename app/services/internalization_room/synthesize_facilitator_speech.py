from __future__ import annotations

import httpx

from app.core.config import Settings, get_settings
from app.services.platform.tts import SpeechStore, SynthesizedSpeech
from app.services.platform.tts import synthesize_speech as platform_speech


async def synthesize_facilitator_speech(
    text: str,
    *,
    client: httpx.AsyncClient | None = None,
    store: SpeechStore | None = None,
    settings: Settings | None = None,
) -> tuple[SynthesizedSpeech, bool]:
    """Speak one facilitator line in the internalization room's own voice.

    The room has a single voice for every line the team hears, so the voice and language
    are server-side configuration rather than request parameters — the app never chooses
    how the facilitator sounds.

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
    speech = await platform_speech(
        text,
        language=cfg.internalization_room_language_code,
        voice_id=cfg.internalization_room_voice_id,
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
