from fastapi import APIRouter, Depends, File, Form, Request, UploadFile

from app.core.auth_middleware import get_current_user
from app.core.exceptions import ValidationError
from app.core.rate_limit import bearer_token_key, limiter
from app.db.models.auth import User
from app.models.platform import SttTranscribeResponse
from app.services.platform.stt import WEBM, transcribe_speech

router = APIRouter()

#: Same ceiling as the two audio endpoints already in the repo (translation_helper,
#: project_health): a spoken answer is seconds long, so this is a guard against the wrong
#: file being sent, not an expected size.
MAX_AUDIO_BYTES = 25 * 1024 * 1024

#: This route bills per second of audio. The cap is sized for a human recording answers one
#: at a time — a bulk pass over a whole session is the batch job's business, not this one's,
#: and that one never comes through here.
STT_RATE_LIMIT_PER_MINUTE = 30


@router.post("/stt/transcribe", response_model=SttTranscribeResponse)
@limiter.limit(f"{STT_RATE_LIMIT_PER_MINUTE}/minute", key_func=bearer_token_key)
async def transcribe_endpoint(
    request: Request,
    file: UploadFile = File(...),
    language: str = Form(...),
    mime_type: str | None = Form(default=None),
    _: User = Depends(get_current_user),
) -> SttTranscribeResponse:
    """Transcribe one recording. Multipart in, text out.

    The single-shot counterpart of `/tts/speak`, and the shape the two existing audio
    endpoints already take, so migrating them here later is a change of URL rather than of
    client. Transcription only: whoever needs English calls the translator, and no app pays
    an LLM by accident on a route named `transcribe`.

    `language` is required. It is the transcriber's hint, and leaving the engine to guess is
    how a Portuguese answer comes back as phonetic Spanish.
    """
    audio = await file.read()
    if len(audio) > MAX_AUDIO_BYTES:
        raise ValidationError("Audio payload exceeds 25 MB limit")

    text = await transcribe_speech(
        audio, language=language, mime_type=mime_type or file.content_type or WEBM
    )
    return SttTranscribeResponse(text=text)
