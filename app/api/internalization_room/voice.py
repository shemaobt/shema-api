from hashlib import sha256

from fastapi import APIRouter, Response

from app.api.internalization_room._deps import room_caller_dep
from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.services.internalization_room.questions import AUDIO_MIME
from app.services.internalization_room.voice_handles import from_handle
from app.services.platform.storage import GcsPlatformStore
from app.services.platform.tts import MIME_TYPE, fetch_clip

router = APIRouter()

IMMUTABLE = "private, max-age=31536000, immutable"


@router.get("/voice/{handle}", dependencies=[room_caller_dep])
async def clip(handle: str) -> Response:
    """Serve one synthesized line by the handle a turn handed out.

    The key behind the handle is content-addressed, so these bytes can never change: the
    app may keep them for as long as it has room, and a line it has already heard costs
    nothing to hear again.
    """
    cfg = get_settings()
    key = from_handle(handle, settings=cfg)
    if key is None:
        raise NotFoundError("No such clip")
    audio = await fetch_clip(key, store=GcsPlatformStore(cfg))
    if audio is None:
        raise NotFoundError("No such clip")
    return Response(
        content=audio,
        media_type=_media_type(key),
        headers={"Cache-Control": IMMUTABLE, "ETag": sha256(audio).hexdigest()[:32]},
    )


def _media_type(key: str) -> str:
    """What the bytes actually are, not what synthesized speech usually is.

    A facilitator records a reply on a phone and it is stored as `audio/mp4`; serving it
    as `audio/mpeg` hands the app a file whose declared type contradicts its contents.
    """
    return AUDIO_MIME if key.endswith(".m4a") else MIME_TYPE
