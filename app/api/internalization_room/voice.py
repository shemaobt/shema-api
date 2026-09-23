import logging
import time
from hashlib import sha256

from fastapi import APIRouter, Depends, Response

from app.api.internalization_room._deps import room_caller_dep
from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.db.models.device import Device
from app.services.internalization_room.questions import AUDIO_MIME
from app.services.internalization_room.synthesize_facilitator_speech import voiced_here
from app.services.internalization_room.voice_handles import from_handle
from app.services.platform.storage import GcsPlatformStore
from app.services.platform.tts import MIME_TYPE, fetch_clip

logger = logging.getLogger(__name__)

router = APIRouter()

IMMUTABLE = "private, max-age=31536000, immutable"


async def _arrived() -> float:
    return time.monotonic()


def _ms(started: float, ended: float) -> int:
    return round((ended - started) * 1000)


@router.get("/voice/{handle}")
async def clip(
    handle: str,
    arrived: float = Depends(_arrived),
    _caller: Device | None = room_caller_dep,
) -> Response:
    """Serve one synthesized line by the handle a turn handed out.

    The key behind the handle is content-addressed, so these bytes can never change: the
    app may keep them for as long as it has room, and a line it has already heard costs
    nothing to hear again.
    """
    cfg = get_settings()
    key = from_handle(handle, settings=cfg)
    if key is None:
        raise NotFoundError("No such clip")
    reading = time.monotonic()
    audio = await fetch_clip(key, store=GcsPlatformStore(cfg))
    read = time.monotonic()
    logger.info(
        "[voice-get] auth=%sms gcs=%sms bytes=%s same_instance=%s",
        _ms(arrived, reading),
        _ms(reading, read),
        len(audio or b""),
        "yes" if voiced_here(key) else "no",
    )
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
