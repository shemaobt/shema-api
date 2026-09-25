from __future__ import annotations

import logging

import httpx

from app.core.config import Settings, get_settings
from app.core.exceptions import UpstreamServiceError, ValidationError
from app.services.project_health.voice.cache import CachedAudio, audio_cache
from app.services.project_health.voice.voice_map import (
    MULTILINGUAL_VOICE_ID,
    resolve_language_hint,
)

logger = logging.getLogger(__name__)


_DEFAULT_CLIENT: httpx.AsyncClient | None = None


def _make_client() -> httpx.AsyncClient:
    global _DEFAULT_CLIENT
    if _DEFAULT_CLIENT is None:
        _DEFAULT_CLIENT = httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0))
    return _DEFAULT_CLIENT


def _require_api_key(cfg: Settings) -> str:
    if not cfg.ph_elevenlabs_api_key:
        raise UpstreamServiceError("PH_ELEVENLABS_API_KEY is not configured")
    return cfg.ph_elevenlabs_api_key


def _upstream_or_validation_error(status_code: int, message: str) -> Exception:
    """Their outage is not our client's bad request — same split as platform/tts.py."""
    if status_code == 429 or status_code >= 500:
        return UpstreamServiceError(message)
    return ValidationError(message)


async def synthesize_speech(
    text: str,
    *,
    language: str,
    settings: Settings | None = None,
    client: httpx.AsyncClient | None = None,
) -> tuple[CachedAudio, bool]:
    """Synthesize MP3 speech via ElevenLabs.

    Returns (cached entry, was cached?). Caches by (language, voice, output
    format, text) so repeated facilitator turns or replays don't re-bill the
    API, and a changed format never serves the old clip.
    """
    if not text or not text.strip():
        raise ValidationError("text must not be empty")

    cfg = settings or get_settings()
    api_key = _require_api_key(cfg)

    cache_key = audio_cache.make_key(
        text, language, MULTILINGUAL_VOICE_ID, cfg.elevenlabs_output_format
    )
    cached = audio_cache.get(cache_key)
    if cached is not None:
        return cached, True

    language_hint = resolve_language_hint(language)
    body: dict[str, object] = {
        "text": text,
        "model_id": cfg.elevenlabs_tts_model,
    }
    if language_hint:
        body["language_code"] = language_hint

    url = f"{cfg.elevenlabs_base_url}/v1/text-to-speech/{MULTILINGUAL_VOICE_ID}"
    headers = {
        "xi-api-key": api_key,
        "accept": "audio/mpeg",
    }

    http = client or _make_client()
    try:
        response = await http.post(
            url, json=body, params={"output_format": cfg.elevenlabs_output_format}, headers=headers
        )
    except httpx.HTTPError as error:
        logger.warning("ElevenLabs TTS unreachable: %s", error)
        raise UpstreamServiceError(f"Speech request could not reach ElevenLabs: {error}") from error
    if response.status_code >= 400:
        logger.warning(
            "ElevenLabs TTS failed: status=%s body=%s",
            response.status_code,
            response.text[:500],
        )
        raise _upstream_or_validation_error(
            response.status_code, f"TTS request failed with status {response.status_code}"
        )

    entry = audio_cache.put(cache_key, response.content, mime_type="audio/mpeg")
    return entry, False


def _sniff_mime(audio_bytes: bytes) -> str | None:
    if len(audio_bytes) < 12:
        return None
    head = audio_bytes[:12]
    if head[0:4] == b"RIFF" and head[8:12] == b"WAVE":
        return "audio/wav"
    if head[0:4] == b"OggS":
        return "audio/ogg"
    if head[0:3] == b"ID3":
        return "audio/mp3"
    if head[0] == 0xFF and (head[1] & 0xE0) == 0xE0:
        return "audio/mp3"
    if head[0:4] == b"\x1a\x45\xdf\xa3":
        return "audio/webm"
    return None


def _guess_mime(filename: str | None, fallback: str | None) -> str:
    if filename:
        lower = filename.lower()
        if lower.endswith(".mp3"):
            return "audio/mp3"
        if lower.endswith(".wav"):
            return "audio/wav"
        if lower.endswith(".m4a"):
            return "audio/mp4"
        if lower.endswith(".webm"):
            return "audio/webm"
        if lower.endswith(".ogg"):
            return "audio/ogg"
    return fallback or "audio/webm"


def _upload_filename(filename: str | None, mime: str) -> str:
    if filename:
        return filename
    ext = {
        "audio/wav": "wav",
        "audio/ogg": "ogg",
        "audio/mp3": "mp3",
        "audio/mpeg": "mp3",
        "audio/mp4": "m4a",
        "audio/webm": "webm",
    }.get(mime, "bin")
    return f"upload.{ext}"


async def transcribe_audio(
    audio_bytes: bytes,
    *,
    language: str | None = None,
    filename: str | None = None,
    mime_type: str | None = None,
    settings: Settings | None = None,
    client: httpx.AsyncClient | None = None,
) -> str:
    if not audio_bytes:
        raise ValidationError("Audio payload is empty")

    cfg = settings or get_settings()
    api_key = _require_api_key(cfg)

    resolved_mime = _guess_mime(filename, mime_type)
    if resolved_mime == "audio/webm" and not filename and not mime_type:
        sniffed = _sniff_mime(audio_bytes)
        if sniffed is not None:
            resolved_mime = sniffed

    upload_name = _upload_filename(filename, resolved_mime)
    data: dict[str, str] = {"model_id": cfg.elevenlabs_stt_model}
    hint = resolve_language_hint(language)
    if hint:
        data["language_code"] = hint

    http = client or _make_client()
    try:
        response = await http.post(
            f"{cfg.elevenlabs_base_url}/v1/speech-to-text",
            headers={"xi-api-key": api_key, "accept": "application/json"},
            files={"file": (upload_name, audio_bytes, resolved_mime)},
            data=data,
        )
    except httpx.HTTPError as error:
        logger.warning("ElevenLabs STT unreachable: %s", error)
        raise UpstreamServiceError(
            f"Transcription request could not reach ElevenLabs: {error}"
        ) from error
    if response.status_code >= 400:
        logger.warning(
            "ElevenLabs STT failed: status=%s body=%s",
            response.status_code,
            response.text[:500],
        )
        raise _upstream_or_validation_error(
            response.status_code,
            f"Transcription request failed with status {response.status_code}",
        )

    payload = response.json()
    text = (payload.get("text") or "").strip()
    if not text:
        raise ValidationError("Transcription returned empty text")
    return text
