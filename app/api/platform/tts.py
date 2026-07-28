from fastapi import APIRouter, Depends, Request, Response

from app.core.auth_middleware import get_current_user
from app.core.rate_limit import bearer_token_key, limiter
from app.db.models.auth import User
from app.models.platform import TtsSpeakRequest
from app.services.platform.tts import synthesize_speech

router = APIRouter()

#: This route bills per character. Because the cache key is content-addressed, random text is
#: a guaranteed miss: every iteration of a runaway retry loop is a paid ElevenLabs call and a
#: new bucket object. Sized to let a cache warm-up (21 questions x 2 languages) run in a
#: couple of minutes while keeping the blast radius of a bad SPA retry bounded.
TTS_RATE_LIMIT_PER_MINUTE = 30


@router.post(
    "/tts/speak",
    response_class=Response,
    responses={200: {"content": {"audio/mpeg": {}}, "description": "Synthesized MP3"}},
)
@limiter.limit(f"{TTS_RATE_LIMIT_PER_MINUTE}/minute", key_func=bearer_token_key)
async def speak_endpoint(
    request: Request,
    payload: TtsSpeakRequest,
    _: User = Depends(get_current_user),
) -> Response:
    """Speak a text: returns the RAW MP3 (not base64-in-JSON).

    Base64 inflates a ~100 KB body by 33% and forces a JSON parse to reach bytes. Worse, on
    the SPA side a JSON envelope would require a new DTO in `contracts/`, which is a frozen
    layer there with mandatory human review. Raw bytes keep the consumer simple.
    """
    speech = await synthesize_speech(payload.text, language=payload.language)
    return Response(
        content=speech.audio,
        media_type=speech.mime_type,
        headers={
            "ETag": speech.etag,
            # Content is hash-addressed: same key => same bytes, always.
            "Cache-Control": "private, max-age=86400, immutable",
            # Makes cache warming observable: did it hit the bucket or ElevenLabs?
            "X-Tts-Cached": "1" if speech.cached else "0",
        },
    )
