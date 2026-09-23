import asyncio
import logging
import re
import time
from dataclasses import dataclass

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
from app.services.platform.tts import MIME_TYPE, SpeechStore, Voicing, etag_of, fetch_clip

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


@dataclass(frozen=True)
class ByteRange:
    start: int
    #: Inclusive, the way `Content-Range` counts it.
    end: int


class RangeNotSatisfiable(Exception):
    pass


_RANGE_RE = re.compile(r"^bytes=(\d*)-(\d*)$")


def _resolve_range(range_header: str | None, *, total: int) -> ByteRange | None:
    """The single byte range this request asks for, or `None` to serve the whole clip.

    Raises `RangeNotSatisfiable` for a range this function understands but that names no
    byte the clip actually has.
    """
    if range_header is None:
        return None
    match = _RANGE_RE.match(range_header.strip())
    if match is None:
        return None
    first, last = match.group(1), match.group(2)
    if first == "":
        if last == "":
            return None
        if int(last) <= 0:
            raise RangeNotSatisfiable()
        return ByteRange(start=max(total - int(last), 0), end=total - 1)
    start = int(first)
    if last and int(last) < start:
        return None
    if start >= total:
        raise RangeNotSatisfiable()
    end = min(int(last), total - 1) if last else total - 1
    return ByteRange(start=start, end=end)


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
    x_range: str | None = Header(default=None, alias="Range"),
    x_if_range: str | None = Header(default=None, alias="If-Range"),
) -> Response:
    """Serve one synthesized line by its handle alone, only as the bucket already keeps it.

    The lines handed out this way are made before the handle is: a prepared opening, a
    passage's name, a line said again, an opening the record dropped. So this route voices
    nothing and joins no flight — with no session it cannot tell whose line a handle is,
    and a turn's own line is served by `turn_clip`. A bucket that cannot be read is a 502,
    an outage, not a missing clip.

    The key behind the handle is content-addressed, so these bytes can never change: the
    app may keep them for as long as it has room, and a line it has already heard costs
    nothing to hear again. The key names the words, though, not one rendering of them. The
    bucket keeps the first rendering written under a key and memory keeps only what the
    bucket confirmed, and the ETag still hashes the bytes actually served, so an `If-Range`
    resume that lands on another rendering gets the whole clip, never a slice spliced onto
    the first.

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

    A 416 is the one answer decided by the `Range` header alone, so it is sent `no-store`:
    stored as immutable under the handle, it kept a tablet refusing a clip it can play.
    """
    return await _serve(
        handle,
        None,
        arrived=arrived,
        db=db,
        x_device_credential=x_device_credential,
        x_room_key=x_room_key,
        x_range=x_range,
        x_if_range=x_if_range,
    )


@router.get("/voice/{session_id}/{handle}")
async def turn_clip(
    session_id: str,
    handle: str,
    arrived: float = Depends(_arrived),
    db: AsyncSession = Depends(get_db),
    x_device_credential: str | None = Header(default=None, alias=DEVICE_CREDENTIAL_HEADER),
    x_room_key: str | None = Header(default=None),
    x_range: str | None = Header(default=None, alias="Range"),
    x_if_range: str | None = Header(default=None, alias="If-Range"),
) -> Response:
    """Serve a line the session said, making it if nothing holds it.

    The session is resolved against the caller's team, and the handle has to be one of that
    session's lines — the Guide's words or one of the opening's two movements — before any
    flight, memory or bucket is consulted; anything else is a 404. A line still being
    voiced on this instance is joined, not voiced again. When no flight, memory or bucket
    holds it, the line is made once from the session's words, and a line that cannot be
    made is a 502, which the app treats as an outage. Neither the wait on a flight nor the
    making outlasts the turn's own bound; running out is a 502 too, and the shielded flight
    still lands for the next request. A bucket read that fails counts as a miss.

    One re-synthesis per GET, not per line: requests racing on one line join the same
    flight. With the bucket refusing every write, nothing is ever confirmed, so each GET
    pays one synthesis and answers 502 — bounded per request, not across a tablet's
    retries, and accepted.
    """
    return await _serve(
        handle,
        session_id,
        arrived=arrived,
        db=db,
        x_device_credential=x_device_credential,
        x_room_key=x_room_key,
        x_range=x_range,
        x_if_range=x_if_range,
    )


async def _serve(
    handle: str,
    session_id: str | None,
    *,
    arrived: float,
    db: AsyncSession,
    x_device_credential: str | None,
    x_room_key: str | None,
    x_range: str | None,
    x_if_range: str | None,
) -> Response:
    cfg = get_settings()
    key = from_handle(handle, settings=cfg)
    flight = in_flight(key) if key is not None and session_id is not None else None
    read_task: asyncio.Task[tuple[bytes | None, int]] | None = None
    if key is not None and flight is None and not _SPECULATIVE_READS.locked():
        await _SPECULATIVE_READS.acquire()
        read_task = _speculate(key, store=GcsPlatformStore(cfg))

    gate_passed = False
    voice: Voicing | None = None
    try:
        caller = await require_room_caller(
            db, x_device_credential=x_device_credential, x_room_key=x_room_key
        )
        if session_id is not None and key is not None:
            session = (
                await room.get_session_for_room_caller(db, session_id, caller.project_id)
                if caller is not None and caller.project_id is not None
                else await room.get_session(db, session_id)
            )
            voice = _voice_of(session, key)
            if voice is None:
                raise NotFoundError("No such clip")
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
    deadline = asyncio.get_running_loop().time() + cfg.internalization_room_turn_bound_ms / 1000
    flight_ms = 0
    if flight is not None:
        audio, gcs_ms = await _landed(flight, deadline), 0
        flight_ms = _ms(authed, time.monotonic())
    else:
        try:
            audio, gcs_ms = await (read_task or _timed_fetch_clip(key, store=GcsPlatformStore(cfg)))
        except Exception as error:
            if voice is None:
                raise UpstreamServiceError("o clipe não pôde ser lido") from error
            audio, gcs_ms = None, 0
    if audio is None and voice is not None:
        flying = time.monotonic()
        try:
            async with asyncio.timeout_at(deadline):
                audio = await asyncio.shield(fly(key, voice))
        except Exception as error:
            raise UpstreamServiceError("a voz desta fala não pôde ser feita") from error
        flight_ms += _ms(flying, time.monotonic())

    etag = etag_of(audio) if audio is not None else ""
    byte_range: ByteRange | None = None
    unsatisfiable = False
    if audio is not None:
        range_header = None if x_if_range is not None and x_if_range != etag else x_range
        try:
            byte_range = _resolve_range(range_header, total=len(audio))
        except RangeNotSatisfiable:
            unsatisfiable = True

    if unsatisfiable or audio is None:
        served = "none"
    elif byte_range is None:
        served = "full"
    else:
        served = f"{byte_range.start}-{byte_range.end}"

    logger.info(
        "[voice-get] auth=%sms flight=%sms gcs=%sms bytes=%s same_instance=%s range=%s",
        _ms(arrived, authed),
        flight_ms,
        gcs_ms,
        len(audio or b""),
        "yes" if voiced_here(key) else "no",
        served,
    )
    if audio is None:
        raise NotFoundError("No such clip")
    if unsatisfiable:
        return Response(
            status_code=416,
            headers={
                "Cache-Control": "no-store",
                "ETag": etag,
                "Accept-Ranges": "bytes",
                "Content-Range": f"bytes */{len(audio)}",
            },
        )
    if byte_range is not None:
        return Response(
            content=audio[byte_range.start : byte_range.end + 1],
            media_type=_media_type(key),
            status_code=206,
            headers={
                "Cache-Control": IMMUTABLE,
                "ETag": etag,
                "Accept-Ranges": "bytes",
                "Content-Range": f"bytes {byte_range.start}-{byte_range.end}/{len(audio)}",
            },
        )
    return Response(
        content=audio,
        media_type=_media_type(key),
        headers={
            "Cache-Control": IMMUTABLE,
            "ETag": etag,
            "Accept-Ranges": "bytes",
        },
    )


def _voice_of(session: IRSession, key: str) -> Voicing | None:
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


async def _landed(flight: asyncio.Task[bytes], deadline: float) -> bytes | None:
    try:
        async with asyncio.timeout_at(deadline):
            return await asyncio.shield(flight)
    except TimeoutError as spent:
        raise UpstreamServiceError("a voz desta fala não ficou pronta a tempo") from spent
    except Exception:
        return None


def _media_type(key: str) -> str:
    """What the bytes actually are, not what synthesized speech usually is.

    A facilitator records a reply on a phone and it is stored as `audio/mp4`; serving it
    as `audio/mpeg` hands the app a file whose declared type contradicts its contents.
    """
    return AUDIO_MIME if key.endswith(".m4a") else MIME_TYPE
