import logging

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile

from app.core.auth_middleware import get_current_user
from app.core.exceptions import UpstreamServiceError, ValidationError
from app.core.rate_limit import bearer_token_key, limiter
from app.db.models.auth import User
from app.models.platform import SttTranscribeResponse
from app.services.platform.disfluency import clean_disfluency
from app.services.platform.stt import WEBM, transcribe_speech

logger = logging.getLogger(__name__)

router = APIRouter()

#: Same ceiling as the two audio endpoints already in the repo (translation_helper,
#: project_health): a spoken answer is seconds long, so this is a guard against the wrong
#: file being sent, not an expected size.
MAX_AUDIO_BYTES = 25 * 1024 * 1024

#: This route bills per second of audio. The cap is sized for a human recording answers one
#: at a time — a bulk pass over a whole session is the batch job's business, not this one's,
#: and that one never comes through here.
#:
#: `clean=true` adds a second provider call per request and the cap is unchanged: it is a
#: text-length call on at most a few minutes of speech, next to a transcription billed per
#: second of audio, so it does not move what this limit was sized against. What the flag
#: does move is latency, and a caller waiting on two providers in series is self-limiting
#: long before thirty a minute.
STT_RATE_LIMIT_PER_MINUTE = 30


@router.post("/stt/transcribe", response_model=SttTranscribeResponse)
@limiter.limit(f"{STT_RATE_LIMIT_PER_MINUTE}/minute", key_func=bearer_token_key)
async def transcribe_endpoint(
    request: Request,
    file: UploadFile = File(...),
    language: str = Form(...),
    mime_type: str | None = Form(default=None),
    clean: bool = Form(default=False),
    _: User = Depends(get_current_user),
) -> SttTranscribeResponse:
    """Transcribe one recording. Multipart in, text out.

    The single-shot counterpart of `/tts/speak`, and the shape the two existing audio
    endpoints already take, so migrating them here later is a change of URL rather than of
    client. Transcription only unless asked otherwise: whoever needs English calls the
    translator, and no app pays an LLM by accident on a route named `transcribe`.

    `clean` is that asking, and it defaults to off for exactly the reason above. Left alone
    it is byte-for-byte the old route and the cleanup provider is never reached. Set, the
    verbatim transcript goes through the same disfluency cleaner the Sound Necklace pass
    uses, in the request's own language — the step is language-agnostic — and the caller gets
    a usable draft in one round trip instead of two.

    A cleanup that cannot be had costs the cleaning and nothing else: the verbatim transcript
    comes back under `cleaned: false`, so the caller is told which of the two it holds rather
    than left to guess from the text. Failing instead would throw away a transcription that
    succeeded and was billed. The cleaner refuses a reply too short to be cleaning as readily
    as it refuses an outage, and a short, hesitant answer trips that honestly — a 502 there
    would report a provider failure that never happened. A missing cleanup key lands here
    too: our misconfiguration, on a provider the transcription never touched.

    Only the cleanup is optional. A transcription failure is still the upstream error it is.

    `language` is required. It is the transcriber's hint, and leaving the engine to guess is
    how a Portuguese answer comes back as phonetic Spanish.
    """
    audio = await file.read()
    if len(audio) > MAX_AUDIO_BYTES:
        raise ValidationError("Audio payload exceeds 25 MB limit")

    text = await transcribe_speech(
        audio, language=language, mime_type=mime_type or file.content_type or WEBM
    )
    if not clean:
        return SttTranscribeResponse(text=text)

    try:
        cleaned = await clean_disfluency(text, language=language)
    except (UpstreamServiceError, ValidationError) as exc:
        logger.warning("stt cleanup skipped, returning the verbatim transcript: %s", exc)
        return SttTranscribeResponse(text=text)
    return SttTranscribeResponse(text=cleaned, cleaned=True)
