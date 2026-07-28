"""Platform speech synthesis (ElevenLabs), shared across apps.

Text + language -> MP3. The cache is **durable, in the generic bucket**, under a
content-addressed key — so every phrase is synthesized **once, forever, for every app**, and
a cold worker does not pay ElevenLabs again. That is the difference from the two clients
already in the repo (`project_health/voice/` and `translation_helper/synthesize_speech.py`),
which carry the SAME copy-pasted `AudioCache` class: an in-process LRU, 100 entries, 24h TTL,
that evaporates on every deploy.

> Those two do **not** use this service yet — migrating them is a follow-up (the
> project_health voice module has no tests today and is live product). Until then the repo
> has three paths to ElevenLabs, and that is known debt, not an oversight.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.core.config import Settings, get_settings
from app.core.exceptions import UpstreamServiceError, ValidationError
from app.services.platform.voices import language_hint, resolve_voice

logger = logging.getLogger(__name__)

MIME_TYPE = "audio/mpeg"

_DEFAULT_CLIENT: httpx.AsyncClient | None = None


@dataclass(frozen=True)
class SynthesizedSpeech:
    audio: bytes
    mime_type: str
    etag: str
    #: Came from the bucket (ElevenLabs was not called).
    cached: bool


class SpeechStore(Protocol):
    """The bucket seam: tests pass an in-memory dict, no GCS."""

    async def get(self, key: str) -> bytes | None: ...

    async def put(self, key: str, data: bytes, content_type: str) -> None: ...


def cache_key(text: str, *, voice_id: str, model: str, output_format: str) -> str:
    """Content-addressed key: same text + voice + model + format = same object.

    Every input that changes the bytes belongs here. `output_format` in particular: leave it
    out and changing the setting keeps serving the old clip in the old format forever, with
    the hardcoded MIME_TYPE hiding the mismatch.
    """
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"tts/{voice_id}/{model}/{output_format}/{digest}.mp3"


async def synthesize_speech(
    text: str,
    *,
    language: str,
    settings: Settings | None = None,
    client: httpx.AsyncClient | None = None,
    store: SpeechStore | None = None,
) -> SynthesizedSpeech:
    """Speak `text` in `language` (BCP-47 locale, e.g. `pt-BR`), serving from cache when possible.

    `settings`, `client` and `store` are injectable — that is what makes the service testable
    without network and without GCS.
    """
    if not text or not text.strip():
        raise ValidationError("text must not be empty")

    cfg = settings or get_settings()
    if not cfg.elevenlabs_api_key:
        # ponytail: project_health uses a SECOND key (`ph_elevenlabs_api_key`). When it
        # migrates here, the two become one.
        raise ValidationError("ELEVENLABS_API_KEY is not configured")

    voice_id = resolve_voice(language)
    key = cache_key(
        text,
        voice_id=voice_id,
        model=cfg.elevenlabs_tts_model,
        output_format=cfg.elevenlabs_output_format,
    )
    speech_store = store or _default_store(cfg)

    cached = await speech_store.get(key)
    if cached is not None:
        return SynthesizedSpeech(cached, MIME_TYPE, _etag(cached), cached=True)

    audio = await _synthesize(text, voice_id=voice_id, language=language, cfg=cfg, client=client)
    await _cache_quietly(speech_store, key, audio)
    return SynthesizedSpeech(audio, MIME_TYPE, _etag(audio), cached=False)


async def _cache_quietly(store: SpeechStore, key: str, audio: bytes) -> None:
    """Store the clip, but never fail the request over it.

    We already paid ElevenLabs for these bytes. A missing bucket or a wrong IAM binding is
    an infrastructure problem — throwing a 500 here would bill the synthesis and hand the
    caller nothing.
    """
    try:
        await store.put(key, audio, MIME_TYPE)
    except Exception:
        logger.exception("failed to cache TTS clip key=%s", key)


async def _synthesize(
    text: str,
    *,
    voice_id: str,
    language: str,
    cfg: Settings,
    client: httpx.AsyncClient | None,
) -> bytes:
    body: dict[str, object] = {
        "text": text,
        "model_id": cfg.elevenlabs_tts_model,
        "output_format": cfg.elevenlabs_output_format,
        "language_code": language_hint(language),
        # ponytail: no `voice_settings` — the voice defaults are fine for a short, neutral
        # question. The calibration knob, if speech ever sounds rushed in an interview, is
        # `"voice_settings": {"speed": 0.9}` (useful range 0.7-1.2, default 1.0).
    }

    http = client or _make_client()
    response = await http.post(
        f"{cfg.elevenlabs_base_url}/v1/text-to-speech/{voice_id}",
        json=body,
        headers={"xi-api-key": cfg.elevenlabs_api_key, "accept": MIME_TYPE},
    )
    if response.status_code >= 400:
        logger.warning(
            "ElevenLabs TTS failed: status=%s body=%s",
            response.status_code,
            response.text[:500],
        )
        raise _upstream_or_validation_error(response.status_code)

    return bytes(response.content)


def _upstream_or_validation_error(status_code: int) -> Exception:
    """Their outage is not our client's bad request.

    429 and 5xx mean ElevenLabs is rate limiting or down: that is an upstream failure (502),
    and dressing it as a 400 means the right alert never fires. Other 4xx really are a
    malformed request we sent, so they stay a business error.
    """
    message = f"TTS request failed with status {status_code}"
    if status_code == 429 or status_code >= 500:
        return UpstreamServiceError(message)
    return ValidationError(message)


def _etag(audio: bytes) -> str:
    return hashlib.sha256(audio).hexdigest()[:32]


def _default_store(cfg: Settings) -> SpeechStore:
    from app.services.platform.storage import GcsPlatformStore

    return GcsPlatformStore(cfg)


def _make_client() -> httpx.AsyncClient:
    global _DEFAULT_CLIENT
    if _DEFAULT_CLIENT is None:
        _DEFAULT_CLIENT = httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0))
    return _DEFAULT_CLIENT
