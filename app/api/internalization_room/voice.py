import asyncio
import contextlib
import logging
import time
from hashlib import sha256

from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room._deps import DEVICE_CREDENTIAL_HEADER, require_room_caller
from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.services.internalization_room.questions import AUDIO_MIME
from app.services.internalization_room.synthesize_facilitator_speech import voiced_here
from app.services.internalization_room.voice_handles import from_handle
from app.services.platform.storage import GcsPlatformStore
from app.services.platform.tts import MIME_TYPE, SpeechStore, fetch_clip

logger = logging.getLogger(__name__)

router = APIRouter()

IMMUTABLE = "private, max-age=31536000, immutable"


async def _arrived() -> float:
    return time.monotonic()


def _ms(started: float, ended: float) -> int:
    return round((ended - started) * 1000)


async def _timed_fetch_clip(key: str, *, store: SpeechStore) -> tuple[bytes | None, int]:
    started = time.monotonic()
    audio = await fetch_clip(key, store=store)
    return audio, _ms(started, time.monotonic())


@router.get("/voice/{handle}")
async def clip(
    handle: str,
    arrived: float = Depends(_arrived),
    db: AsyncSession = Depends(get_db),
    x_device_credential: str | None = Header(default=None, alias=DEVICE_CREDENTIAL_HEADER),
    x_room_key: str | None = Header(default=None),
) -> Response:
    """Serve one synthesized line by the handle a turn handed out.

    The key behind the handle is content-addressed, so these bytes can never change: the
    app may keep them for as long as it has room, and a line it has already heard costs
    nothing to hear again.

    The device check runs beside the read, not before it — the two are independent, and a
    tablet that is still welcome pays for whichever one is slower, not their sum. A refusal
    cancels the read; a read that had already failed on its own is discarded rather than
    reported, because the caller's own credential is why this request ends, not the bucket.
    """
    cfg = get_settings()
    key = from_handle(handle, settings=cfg)
    if key is None:
        raise NotFoundError("No such clip")
    read_task = asyncio.create_task(_timed_fetch_clip(key, store=GcsPlatformStore(cfg)))
    try:
        await require_room_caller(db, x_device_credential, x_room_key)
    except Exception:
        read_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await read_task
        raise
    authed = time.monotonic()
    audio, gcs_ms = await read_task
    logger.info(
        "[voice-get] auth=%sms gcs=%sms bytes=%s same_instance=%s",
        _ms(arrived, authed),
        gcs_ms,
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
