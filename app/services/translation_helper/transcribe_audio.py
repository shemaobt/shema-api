from __future__ import annotations

import logging
import math

import httpx

from app.core.config import Settings, get_settings
from app.core.exceptions import ValidationError

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

    The internalization room reads the detected language and confidence to tell
    mother-tongue practice apart from bridge speech and to under-count uncertain
    transcripts; plain callers keep receiving just the text.
    """

    def __init__(
        self,
        *,
        text: str,
        language_code: str | None = None,
        language_probability: float | None = None,
        transcript_confidence: float | None = None,
    ) -> None:
        self.text = text
        self.language_code = language_code
        self.language_probability = language_probability
        self.transcript_confidence = transcript_confidence


def _transcript_confidence(words: list[dict]) -> float | None:
    """Mean word log-probability folded back to a probability, used only to under-count:
    an uncertain transcript is repeated, never judged as misunderstanding."""
    logprobs = [
        word["logprob"]
        for word in words
        if isinstance(word, dict)
        and word.get("type") == "word"
        and isinstance(word.get("logprob"), (int, float))
        and math.isfinite(word["logprob"])
    ]
    if not logprobs:
        return None
    return math.exp(sum(logprobs) / len(logprobs))


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
        raise ValidationError("ELEVENLABS_API_KEY is not configured")

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
    response = await http.post(
        f"{cfg.elevenlabs_base_url}/v1/speech-to-text",
        headers={"xi-api-key": cfg.elevenlabs_api_key, "accept": "application/json"},
        files={"file": (upload_name, audio_bytes, resolved_mime)},
        data={"model_id": cfg.elevenlabs_stt_model},
    )
    if response.status_code >= 400:
        logger.warning(
            "ElevenLabs STT failed: status=%s body=%s",
            response.status_code,
            response.text[:500],
        )
        raise ValidationError(f"Transcription request failed with status {response.status_code}")

    payload = response.json()
    text = (payload.get("text") or "").strip()
    if not text:
        raise ValidationError("Transcription returned empty text")
    probability = payload.get("language_probability")
    return TranscriptionResult(
        text=text,
        language_code=payload.get("language_code") or None,
        language_probability=float(probability) if isinstance(probability, (int, float)) else None,
        transcript_confidence=_transcript_confidence(payload.get("words") or []),
    )


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
