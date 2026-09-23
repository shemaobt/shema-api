import asyncio
import logging
import time
from collections.abc import Callable, Coroutine
from hashlib import sha256
from typing import Any

from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room._deps import DEVICE_CREDENTIAL_HEADER, require_room_caller
from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import NotFoundError, UpstreamServiceError
from app.db.models.internalization_room import IRSession
from app.services import internalization_room as room
from app.services.internalization_room.clip_flight import fly, in_flight
from app.services.internalization_room.questions import AUDIO_MIME
from app.services.internalization_room.synthesize_facilitator_speech import voiced_here
from app.services.internalization_room.voice_handles import from_handle
from app.services.platform.storage import GcsPlatformStore
from app.services.platform.tts import MIME_TYPE, SpeechStore, fetch_clip

logger = logging.getLogger(__name__)

router = APIRouter()

IMMUTABLE = "private, max-age=31536000, immutable"

#: Bounds how many clip reads race the device check at once. `GcsPlatformStore` runs the
#: blocking GCS call on `asyncio.to_thread`, the same default executor the room's voice
#: uploads share — a burst of requests carrying a bad or missing credential must not starve
#: it of threads over a read nobody will ever receive. Past this many in flight, a request
#: falls back to reading only once the gate has passed, exactly as it did before this route
#: learned to race the two. Two, because that executor is ``min(32, cpu_count + 4)`` threads,
#: five on a one-vCPU instance, and handles are unsigned: anyone who was ever handed one can
#: mint another under the room's voice, so a junk credential can still buy a read that the
#: gate then refuses. At most two of those at once leaves the uploads their threads.
_SPECULATIVE_READS = asyncio.Semaphore(2)


async def _arrived() -> float:
    return time.monotonic()


def _ms(started: float, ended: float) -> int:
    return round((ended - started) * 1000)


async def _timed_fetch_clip(key: str, *, store: SpeechStore) -> tuple[bytes | None, int]:
    started = time.monotonic()
    audio = await fetch_clip(key, store=store)
    return audio, _ms(started, time.monotonic())


def _speculate(key: str, *, store: SpeechStore) -> asyncio.Task[tuple[bytes | None, int]]:
    """Start the read beside the gate, holding one of the speculative permits for it.

    The permit is held by the read itself, not by whoever awaits it. A refusal cancels the
    awaiting task, but the download underneath runs on a `to_thread` worker that no cancel
    reaches, so the permit is handed back only when that inner read has really ended; handed
    back on the cancel, the bound would count waits instead of threads. A task cancelled
    before its first step — a gate that refuses without awaiting anything — never starts the
    inner read, so the permit comes back through the outer task's own callback instead.
    """
    started: list[asyncio.Future[tuple[bytes | None, int]]] = []

    async def read() -> tuple[bytes | None, int]:
        inner = asyncio.ensure_future(_timed_fetch_clip(key, store=store))
        started.append(inner)
        inner.add_done_callback(_speculation_ended)
        return await asyncio.shield(inner)

    def _never_started(_: asyncio.Task[tuple[bytes | None, int]]) -> None:
        if not started:
            _SPECULATIVE_READS.release()

    outer = asyncio.create_task(read())
    outer.add_done_callback(_never_started)
    return outer


def _speculation_ended(inner: asyncio.Future[tuple[bytes | None, int]]) -> None:
    _SPECULATIVE_READS.release()
    if not inner.cancelled():
        inner.exception()


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
    tablet that is still welcome pays for whichever one is slower, not their sum. But the
    gate always answers first: a handle that does not decode to this room's own voice
    waits behind the same check a good one does, so a caller with no working credential
    cannot tell "not ours" apart from "yours, but refused" by watching which error comes
    back. A refusal cancels the read and discards whatever it turns up — even a hit
    already moved to the front of the in-memory cache's eviction order, which this leaves
    as is rather than teach that cache about requests that were never actually let in.
    Cancelling a read already on its GCS thread only stops the route from waiting on it;
    the download still runs to completion in the background, its bytes discarded.
    """
    return await _serve(
        handle,
        None,
        arrived=arrived,
        db=db,
        x_device_credential=x_device_credential,
        x_room_key=x_room_key,
    )


@router.get("/voice/{session_id}/{handle}")
async def turn_clip(
    session_id: str,
    handle: str,
    arrived: float = Depends(_arrived),
    db: AsyncSession = Depends(get_db),
    x_device_credential: str | None = Header(default=None, alias=DEVICE_CREDENTIAL_HEADER),
    x_room_key: str | None = Header(default=None),
) -> Response:
    return await _serve(
        handle,
        session_id,
        arrived=arrived,
        db=db,
        x_device_credential=x_device_credential,
        x_room_key=x_room_key,
    )


async def _serve(
    handle: str,
    session_id: str | None,
    *,
    arrived: float,
    db: AsyncSession,
    x_device_credential: str | None,
    x_room_key: str | None,
) -> Response:
    cfg = get_settings()
    key = from_handle(handle, settings=cfg)
    flight = in_flight(key) if key is not None else None
    read_task: asyncio.Task[tuple[bytes | None, int]] | None = None
    if key is not None and flight is None and not _SPECULATIVE_READS.locked():
        await _SPECULATIVE_READS.acquire()
        read_task = _speculate(key, store=GcsPlatformStore(cfg))

    gate_passed = False
    session: IRSession | None = None
    try:
        caller = await require_room_caller(
            db, x_device_credential=x_device_credential, x_room_key=x_room_key
        )
        if session_id is not None:
            session = await room.get_session_for_room_caller(
                db, session_id, caller.project_id if caller else None
            )
        gate_passed = True
    finally:
        if not gate_passed and read_task is not None:
            if not read_task.done():
                read_task.cancel()
            await asyncio.wait({read_task})
            if not read_task.cancelled():
                read_task.exception()

    if key is None:
        raise NotFoundError("No such clip")

    authed = time.monotonic()
    flight_ms = 0
    if flight is not None:
        audio, gcs_ms = await _landed(flight), 0
        flight_ms = _ms(authed, time.monotonic())
    elif read_task is None:
        audio, gcs_ms = await _timed_fetch_clip(key, store=GcsPlatformStore(cfg))
    else:
        audio, gcs_ms = await read_task
    if audio is None and session is not None:
        voice = _voice_of(session, key)
        if voice is not None:
            flying = time.monotonic()
            try:
                audio = await asyncio.shield(fly(key, voice))
            except Exception as error:
                raise UpstreamServiceError("a voz desta fala não pôde ser feita") from error
            flight_ms += _ms(flying, time.monotonic())
    logger.info(
        "[voice-get] auth=%sms flight=%sms gcs=%sms bytes=%s same_instance=%s",
        _ms(arrived, authed),
        flight_ms,
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


def _voice_of(session: IRSession, key: str) -> Callable[[], Coroutine[Any, Any, bytes]] | None:
    for message in reversed(session.messages or []):
        if message.get("role") != "guide":
            continue
        for text in (message.get("text", ""), *message.get("movements", [])):
            if not text.strip():
                continue
            line_key, voice = room.facilitator_speech_to_come(text, language=session.language)
            if line_key == key:
                return voice
    return None


async def _landed(flight: asyncio.Task[bytes]) -> bytes | None:
    try:
        return await asyncio.shield(flight)
    except Exception:
        return None


def _media_type(key: str) -> str:
    """What the bytes actually are, not what synthesized speech usually is.

    A facilitator records a reply on a phone and it is stored as `audio/mp4`; serving it
    as `audio/mpeg` hands the app a file whose declared type contradicts its contents.
    """
    return AUDIO_MIME if key.endswith(".m4a") else MIME_TYPE
