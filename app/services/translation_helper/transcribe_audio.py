from __future__ import annotations

import logging

import httpx

from app.core.config import Settings, get_settings
from app.core.exceptions import UpstreamServiceError, ValidationError, upstream_or_validation_error

logger = logging.getLogger(__name__)


def _sniff_mime_from_bytes(audio_bytes: bytes) -> str | None:
    """Best-effort MIME detection from the first few bytes of common audio formats."""
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


def _guess_mime_type(filename: str | None, fallback: str | None) -> str:
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
    if fallback:
        return fallback
    return "audio/mpeg"


def _filename_for_upload(filename: str | None, mime_type: str) -> str:
    if filename:
        return filename
    extension = {
        "audio/wav": "wav",
        "audio/ogg": "ogg",
        "audio/mp3": "mp3",
        "audio/mpeg": "mp3",
        "audio/mp4": "m4a",
        "audio/webm": "webm",
    }.get(mime_type, "bin")
    return f"upload.{extension}"


_DEFAULT_CLIENT: httpx.AsyncClient | None = None


def _make_client() -> httpx.AsyncClient:
    global _DEFAULT_CLIENT
    if _DEFAULT_CLIENT is None:
        _DEFAULT_CLIENT = httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0))
    return _DEFAULT_CLIENT


class TranscriptionResult:
    """One transcription plus the provider metadata some callers need.

    The internalization room reads the detected language to tell mother-tongue practice
    apart from bridge speech; plain callers keep receiving just the text.
    """

    def __init__(
        self,
        *,
        text: str,
        language_code: str | None = None,
        language_probability: float | None = None,
    ) -> None:
        self.text = text
        self.language_code = language_code
        self.language_probability = language_probability


class EmptyTranscription(ValidationError):
    def __init__(self, heard: TranscriptionResult) -> None:
        super().__init__("Transcription returned empty text")
        self.heard = heard


async def transcribe_audio_detailed(
    audio_bytes: bytes,
    *,
    filename: str | None = None,
    mime_type: str | None = None,
    settings: Settings | None = None,
    client: httpx.AsyncClient | None = None,
) -> TranscriptionResult:
    if not audio_bytes:
        raise ValidationError("Audio payload is empty")
    cfg = settings or get_settings()
    if not cfg.elevenlabs_api_key:
        raise UpstreamServiceError("ELEVENLABS_API_KEY is not configured")

    resolved_mime = _guess_mime_type(filename, mime_type)
    if resolved_mime == "audio/mpeg" and not filename and not mime_type:
        sniffed = _sniff_mime_from_bytes(audio_bytes)
        if sniffed is not None:
            resolved_mime = sniffed
        else:
            logger.warning(
                "Audio mime-type fallback hit for transcription: filename=%r mime=%r",
                filename,
                mime_type,
            )

    upload_name = _filename_for_upload(filename, resolved_mime)
    http = client or _make_client()
    try:
        response = await http.post(
            f"{cfg.elevenlabs_base_url}/v1/speech-to-text",
            headers={"xi-api-key": cfg.elevenlabs_api_key, "accept": "application/json"},
            files={"file": (upload_name, audio_bytes, resolved_mime)},
            data={"model_id": cfg.elevenlabs_stt_model},
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
        raise upstream_or_validation_error(
            response.status_code, f"Transcription request failed with status {response.status_code}"
        )

    payload = response.json()
    probability = payload.get("language_probability")
    result = TranscriptionResult(
        text=(payload.get("text") or "").strip(),
        language_code=payload.get("language_code") or None,
        language_probability=float(probability) if isinstance(probability, (int, float)) else None,
    )
    if not result.text:
        raise EmptyTranscription(result)
    return result


async def transcribe_audio(
    audio_bytes: bytes,
    *,
    filename: str | None = None,
    mime_type: str | None = None,
    settings: Settings | None = None,
    client: httpx.AsyncClient | None = None,
) -> str:
    result = await transcribe_audio_detailed(
        audio_bytes,
        filename=filename,
        mime_type=mime_type,
        settings=settings,
        client=client,
    )
    return result.text
