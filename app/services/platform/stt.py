"""Platform speech-to-text (ElevenLabs Scribe), shared across apps.

Audio + the language it was spoken in -> text. Server-side only: the provider key is the
same account as `platform/tts.py` and must never reach a browser.

No cache, unlike the TTS service — and that asymmetry is the point. A synthesized question
is the same bytes for every session forever, so caching it is free money; a recorded answer
is unique by construction, so a content-addressed cache would be an object store of
single-use entries. Re-transcription is instead kept off by the caller, which persists the
draft (`sn_answer_transcripts`) and only asks again on `force`.

> Two other ElevenLabs STT clients already exist (`translation_helper/transcribe_audio.py`
> and `project_health/voice/`), each with its own copy of the multipart call. Migrating them
> here is a follow-up, exactly as it is for TTS — known debt, not an oversight.
"""

from __future__ import annotations

import logging
from typing import Protocol

import httpx

from app.core.config import Settings, get_settings
from app.core.exceptions import UpstreamServiceError, ValidationError
from app.services.platform.voices import language_hint

logger = logging.getLogger(__name__)

WEBM = "audio/webm"

_DEFAULT_CLIENT: httpx.AsyncClient | None = None


class SpeechToText(Protocol):
    """The provider seam: swapping Scribe for another engine is one callable."""

    async def __call__(self, audio: bytes, *, language: str, mime_type: str) -> str: ...


async def transcribe_speech(
    audio: bytes,
    *,
    language: str,
    mime_type: str = WEBM,
    settings: Settings | None = None,
    client: httpx.AsyncClient | None = None,
) -> str:
    """Transcribe `audio` spoken in `language` (BCP-47 locale, e.g. `pt-BR`).

    The language is a HINT, not a detection request: the interview language is known, and
    letting the model guess is how a Portuguese answer comes back as phonetic Spanish.

    Returns the transcript, which may be empty — a take with no speech is an answer state,
    not a failure. `settings` and `client` are injectable so this runs in tests without
    network.

    Usage is logged in bytes rather than in seconds of audio, which is what is billed: the
    duration is not knowable without decoding the container, and the byte count is the
    proxy that costs nothing to measure.
    """
    if not audio:
        raise ValidationError("Audio payload is empty")

    cfg = settings or get_settings()
    if not cfg.elevenlabs_api_key:
        raise ValidationError("ELEVENLABS_API_KEY is not configured")

    http = client or _make_client()
    response = await http.post(
        f"{cfg.elevenlabs_base_url}/v1/speech-to-text",
        headers={"xi-api-key": cfg.elevenlabs_api_key, "accept": "application/json"},
        files={"file": ("answer.webm", audio, mime_type)},
        data={"model_id": cfg.elevenlabs_stt_model, "language_code": language_hint(language)},
    )
    if response.status_code >= 400:
        logger.warning(
            "ElevenLabs STT failed: status=%s body=%s", response.status_code, response.text[:500]
        )
        raise _upstream_or_validation_error(response.status_code)

    text = str(response.json().get("text") or "").strip()
    logger.info(
        "platform STT: model=%s language=%s bytes=%d chars=%d",
        cfg.elevenlabs_stt_model,
        language,
        len(audio),
        len(text),
    )
    return text


def _upstream_or_validation_error(status_code: int) -> Exception:
    """Their outage is not our client's bad request — same split as the TTS service."""
    message = f"Transcription request failed with status {status_code}"
    if status_code == 429 or status_code >= 500:
        return UpstreamServiceError(message)
    return ValidationError(message)


def _make_client() -> httpx.AsyncClient:
    global _DEFAULT_CLIENT
    if _DEFAULT_CLIENT is None:
        _DEFAULT_CLIENT = httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0))
    return _DEFAULT_CLIENT
