from __future__ import annotations

import base64
import hashlib
import logging
import uuid
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from google_crc32c import Checksum
from sqlalchemy import ColumnElement, UnaryExpression, case, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import (
    ERROR_CODE_TAKE_DURATION_DIFFERS,
    ERROR_CODE_TAKE_FINGERPRINT_DIFFERS,
    ERROR_CODE_TAKE_TOO_LONG,
    NotFoundError,
    RecordingRefused,
    StretchNoLongerCounts,
    TakeMoved,
    UnknownReferenceError,
    ValidationError,
)
from app.db.models.auth import User
from app.db.models.internalization_room import (
    IRSceneFrase,
    IRSceneRehearsal,
    IRSession,
    IRTake,
    IRTakeKind,
)
from app.services.oral_collector.gcs_utils import generate_signed_download_url
from app.services.platform.audio_duration import measure_ms_bounded
from app.services.platform.storage import GcsPlatformStore, StoredObject
from app.services.project.reads_project import reads_project

AUDIO_MIME = "audio/mp4"
MAX_TAKE_BYTES = 25 * 1024 * 1024
LISTEN_MINUTES = 15
#: How long a download link lasts, her ``expiresIn: 3600``: a file handed to Refine is not
#: played on the spot, so it outlives the fifteen minutes a listen needs.
DOWNLOAD_LINK_SECONDS = 3600

FILENAMES = {IRTakeKind.ENSAIO: "tomada", IRTakeKind.RETRO: "trecho"}

#: How far the length the tablet sent may sit from the one ffprobe reads off the same bytes:
#: the two read one file through different containers' rounding, never a different sound.
DURATION_SLACK_MS = 100
#: The **Clock offset** worth keeping, her ``CLOCK_SKEW_NOTE_MS``: under five minutes it is a
#: clock set by hand, not one the consultant should hear about.
CLOCK_OFFSET_NOTED_MS = 5 * 60_000
#: The longest length a take can claim: no recording of the room lasts a day, and anything
#: longer is no recording's length.
LONGEST_TAKE_MS = 24 * 60 * 60 * 1000

logger = logging.getLogger(__name__)


def is_wav(content_type: str) -> bool:
    """Marcia's rule for a WAV clip: the content type says ``wav``, in any case.

    Read off the content type and never off the bytes, because that is what her app reads, and
    the release's audio format and a take's file name must agree on what counts.
    """
    return "wav" in content_type.lower()


class TakeStore(Protocol):
    """What a take needs from storage: write it, read it, and ask about it.

    `stat` is the one the platform store did not have. It is what separates "the API
    stored what it received" from "the bucket holds it".
    """

    async def get(self, key: str) -> bytes | None: ...

    async def put(self, key: str, data: bytes, content_type: str) -> bytes: ...

    async def stat(self, key: str) -> StoredObject | None: ...


def _store(settings: Settings | None = None) -> TakeStore:
    return GcsPlatformStore(settings or get_settings())


def take_store() -> TakeStore:
    """The store a route hands the recordings it keeps; a case overrides it as a dependency."""
    return _store()


def extension(content_type: str) -> str:
    return "wav" if is_wav(content_type) else "m4a"


def storage_key(session_id: str, kind: IRTakeKind, sha256: str, content_type: str) -> str:
    """Content-addressed, so a failed upload can only ever leave an orphan.

    A stable key would overwrite in place: a second attempt that dies halfway would leave the
    bucket holding half of the new take under the name of the old one, and nothing would say
    so. Addressed by its own hash, a broken upload is an object nothing points at.

    It also makes the whole path idempotent — the same bytes sent twice land on the same
    object and, by the unique constraint, the same row. The content type only names the file a
    take is first stored under: the same bytes sent again under another one are the same take,
    found by their hash, so a retry never moves the packet's take or mints a version.

    The last segment is the name the take downloads under, so it follows the content type: a
    WAV take is ``.wav`` and anything else keeps the ``.m4a`` it always had.
    """
    return (
        f"internalization-room/takes/{session_id}/{kind.value}/{sha256}/"
        f"{FILENAMES[kind]}.{extension(content_type)}"
    )


def recording_digest(audio: bytes) -> str:
    """The recording's sha256, once it is one the room keeps: some audio, at most 25 MB."""
    if not audio:
        raise ValidationError("A recording with no audio is not a recording")
    if len(audio) > MAX_TAKE_BYTES:
        raise ValidationError("Audio payload exceeds 25 MB limit")
    return hashlib.sha256(audio).hexdigest()


@dataclass(frozen=True)
class CheckedRecording:
    """A recording's hash and the length it keeps, once what the tablet said of it held."""

    sha256: str
    duration_ms: int | None


async def checked_recording(
    audio: bytes, *, sent_sha256: str | None = None, sent_duration_ms: int | None = None
) -> CheckedRecording:
    """Hash and measure the bytes, and refuse a fingerprint or a length they contradict.

    The tablet's length is kept as sent when it is within the slack, or when the bytes cannot be
    measured; a take sent with none keeps the measured one. Bytes that measure past a day are no
    recording's, whoever said so.
    """
    digest = recording_digest(audio)
    if sent_sha256 is not None and sent_sha256.lower() != digest:
        raise RecordingRefused(
            f"The sha256 sent is not the recording's: {digest}",
            ERROR_CODE_TAKE_FINGERPRINT_DIFFERS,
        )
    measured = await measure_ms_bounded(audio)
    if measured is not None and measured > LONGEST_TAKE_MS:
        raise RecordingRefused(
            f"The recording measures {measured} ms, longer than any recording lasts",
            ERROR_CODE_TAKE_TOO_LONG,
        )
    if (
        sent_duration_ms is not None
        and measured is not None
        and abs(sent_duration_ms - measured) > DURATION_SLACK_MS
    ):
        raise RecordingRefused(
            f"The duration_ms sent is not the recording's: it lasts {measured} ms",
            ERROR_CODE_TAKE_DURATION_DIFFERS,
        )
    return CheckedRecording(
        sha256=digest, duration_ms=measured if sent_duration_ms is None else sent_duration_ms
    )


def recording_time(sent_recorded_at: datetime | None, arrived: datetime) -> datetime:
    """The tablet's clock when it sent one, else the server's at the recording's arrival."""
    return arrived if sent_recorded_at is None else sent_recorded_at


def noted_clock_offset(sent_recorded_at: datetime, arrived: datetime) -> int | None:
    """The tablet's clock minus the server's at arrival, in ms, when it is worth keeping."""
    offset = round((sent_recorded_at - arrived).total_seconds() * 1000)
    return None if abs(offset) < CLOCK_OFFSET_NOTED_MS else offset


@dataclass(frozen=True)
class StoredRecording:
    """What the bucket holds under a key, described by the bytes that were stored."""

    storage_key: str
    size_bytes: int
    sha256: str
    crc32c: str
    content_type: str
    verified_at: datetime | None


async def store_recording(
    audio: bytes,
    *,
    key: str,
    sha256: str,
    content_type: str,
    store: TakeStore | None = None,
) -> StoredRecording:
    """Put the bytes in the bucket and read the bucket's own accounting of them back."""
    speech_store = store or _store()
    await speech_store.put(key, audio, content_type)
    crc32c = _crc32c(audio)
    landed = await speech_store.stat(key)
    return StoredRecording(
        storage_key=key,
        size_bytes=len(audio),
        sha256=sha256,
        crc32c=crc32c,
        content_type=content_type,
        verified_at=_verified(landed, size=len(audio), crc32c=crc32c),
    )


def _crc32c(audio: bytes) -> str:
    checksum = Checksum()
    checksum.update(audio)
    return base64.b64encode(checksum.digest()).decode("ascii")


async def store_take(
    db: AsyncSession,
    *,
    session_id: str,
    device_id: str,
    pericope: str,
    kind: IRTakeKind,
    scope: str,
    audio: bytes,
    project_id: str | None = None,
    pass_number: int | None = None,
    ordinal: int | None = None,
    content_type: str = AUDIO_MIME,
    store: TakeStore | None = None,
    origin: str | None = None,
    sent_sha256: str | None = None,
    sent_duration_ms: int | None = None,
    sent_recorded_at: datetime | None = None,
) -> IRTake:
    """Put the bytes in the bucket, read it back, then record where it is.

    That order is deliberate and matches the hand's questions: a row pointing at an object
    that was never written is a take the app believes is safe and nobody can play. The
    reverse — an object with no row — costs storage and nothing else.

    The checksums describe the bytes that were stored, not the bytes that were promised, so
    they are computed here rather than trusted from the request; what the tablet sent of them
    is checked before anything is stored.

    The **Recording time** is the tablet's when it sent one for a take recorded on it, and the
    server's for a joined part, whose tablet time only measures the **Clock offset**. A take sent
    with no time has none of its own: its arrival stands in for one, and both are stamped from
    the same clock reading, which is how a reader tells it apart (`has_its_own_recording_time`). Two
    uploads of the same bytes at once both pass the first look: the unique index refuses the
    second row, and its upload answers with the first. The insert sits in a savepoint, so the
    refusal undoes it alone and leaves the caller's objects as they were.

    The server's clock is read once, before the bytes are measured or stored: the take's
    arrival and its offset are both read on it, so neither counts as the tablet's.
    """
    arrived = datetime.now(UTC)
    checked = await checked_recording(
        audio, sent_sha256=sent_sha256, sent_duration_ms=sent_duration_ms
    )
    key = storage_key(session_id, kind, checked.sha256, content_type)

    already = await _the_same_take(db, session_id, kind, checked.sha256)
    if already is not None:
        return already
    await db.commit()

    stored = await store_recording(
        audio, key=key, sha256=checked.sha256, content_type=content_type, store=store
    )
    offset = (
        noted_clock_offset(sent_recorded_at, arrived)
        if origin is not None and sent_recorded_at is not None
        else None
    )
    if offset is not None:
        logger.warning("A tablet joining in session %s is %d ms off the server", session_id, offset)
    take = IRTake(
        id=str(uuid.uuid4()),
        project_id=project_id,
        session_id=session_id,
        device_id=device_id,
        pericope=pericope,
        kind=kind,
        scope=scope,
        pass_number=pass_number,
        ordinal=ordinal,
        storage_key=stored.storage_key,
        size_bytes=stored.size_bytes,
        sha256=stored.sha256,
        crc32c=stored.crc32c,
        content_type=stored.content_type,
        verified_at=stored.verified_at,
        origin=origin,
        created_at=arrived,
        recorded_at=recording_time(None if origin is not None else sent_recorded_at, arrived),
        duration_ms=checked.duration_ms,
        device_clock_offset_ms=offset,
    )
    try:
        async with db.begin_nested():
            db.add(take)
    except IntegrityError:
        winner = await _the_same_take(db, session_id, kind, checked.sha256)
        if winner is None:
            raise
        return winner
    await db.commit()
    return take


async def the_take_already_kept(
    db: AsyncSession, session_id: str, kind: IRTakeKind, audio: bytes
) -> IRTake | None:
    return await _the_same_take(db, session_id, kind, recording_digest(audio))


async def _the_same_take(
    db: AsyncSession, session_id: str, kind: IRTakeKind, sha256: str
) -> IRTake | None:
    found: IRTake | None = await db.scalar(
        select(IRTake).where(
            IRTake.session_id == session_id, IRTake.kind == kind, IRTake.sha256 == sha256
        )
    )
    return found


def _verified(landed: StoredObject | None, *, size: int, crc32c: str) -> datetime | None:
    """A timestamp only when the bucket's own accounting matches what was sent.

    Not raising is deliberate. The object is there either way, and refusing the request
    would tell the app to keep trying — which re-sends the same bytes to the same
    content-addressed key and reproduces the same mismatch. An unverified row is a row
    somebody can go and look at; a lost take is not.
    """
    if landed is None or landed.size != size or landed.crc32c != crc32c:
        return None
    return datetime.now(UTC)


async def take_by_id(db: AsyncSession, take_id: str) -> IRTake:
    result = await db.execute(select(IRTake).where(IRTake.id == take_id))
    take = result.scalar_one_or_none()
    if take is None:
        raise NotFoundError(_no_such_take(take_id))
    return take


def _no_such_take(take_id: str) -> str:
    """One message for absent, unowned, and somebody else's. See ENG-534."""
    return f"Internalization room take {take_id} not found"


async def take_for_reader(db: AsyncSession, user: User, take_id: str) -> IRTake:
    """The take, if it belongs to a team this user reads.

    The route this guards answers with a signed URL, so what a missing check leaks is not a
    row but the audio itself — and the URL outlives the request that produced it.
    """
    take = await take_by_id(db, take_id)
    if take.project_id is None or not await reads_project(db, user, take.project_id):
        raise NotFoundError(_no_such_take(take_id))
    return take


async def take_in_session(db: AsyncSession, session_id: str, take_id: str) -> IRTake:
    """The take, if it is one of this session's.

    What the room presents is a key shipped inside the app bundle, identical in every
    installation — it names no team. A take resolved by its identifier alone would
    therefore be reachable by anybody holding the app, and the route this guards answers
    with a signed URL, so what leaks is the audio and not a row. Naming the session is
    what keeps a shared credential from being a key to the whole archive.

    The refusal carries `take_by_id`'s message, so somebody else's take and no take at
    all read alike and the answer is no inventory of what exists.
    """
    result = await db.execute(
        select(IRTake).where(IRTake.id == take_id, IRTake.session_id == session_id)
    )
    take = result.scalar_one_or_none()
    if take is None:
        raise NotFoundError(_no_such_take(take_id))
    return take


async def listen_url(
    recording: IRTake | IRSceneRehearsal | IRSceneFrase, *, settings: Settings | None = None
) -> str:
    """A short-lived signed URL to a stored recording, so the bytes never pass through the API.

    A rehearsal take is the whole passage and a scene rehearsal a whole scene; proxying minutes
    of audio through the application server buys nothing over letting storage serve it, and a
    frase is served the same way.
    """
    return await signed_listen_url(recording.storage_key, recording.content_type, settings=settings)


async def signed_listen_url(
    storage_key: str, content_type: str, *, settings: Settings | None = None
) -> str:
    return await signed_url(storage_key, content_type, minutes=LISTEN_MINUTES, settings=settings)


async def signed_url(
    storage_key: str,
    content_type: str,
    *,
    minutes: int,
    disposition: str | None = None,
    settings: Settings | None = None,
) -> str:
    cfg = settings or get_settings()
    if not cfg.gcs_platform_bucket:
        raise ValidationError("GCS_PLATFORM_BUCKET is not configured")
    named = {} if disposition is None else {"response_disposition": disposition}
    return await generate_signed_download_url(
        cfg.gcs_platform_bucket,
        storage_key,
        expiry_minutes=minutes,
        response_content_type=content_type,
        **named,
    )


async def rehearsal_take_of(db: AsyncSession, session_id: str, take_id: str) -> IRTake:
    """The rehearsal recording a stretch claims to have come out of, or a refusal.

    A stretch is a slice of one file, so the file has to be one this session recorded in the
    mother tongue. Checked rather than trusted: a slice of somebody else's recording, or of a
    telling-back, is not a stretch of this passage at all, and stored unchecked it would read
    downstream as one.

    Both callers name this take in the request body, so a miss here is a row the caller named
    that does not exist — the house rule of `UnknownReferenceError` — and not the session gone,
    which the caller already resolved from the path before reaching this call.
    """
    result = await db.execute(
        select(IRTake).where(
            IRTake.id == take_id,
            IRTake.session_id == session_id,
            IRTake.kind == IRTakeKind.ENSAIO,
        )
    )
    take = result.scalar_one_or_none()
    if take is None:
        raise UnknownReferenceError(f"Internalization room rehearsal take {take_id} not found")
    return take


async def refuse_a_take_that_is_no_longer_a_part(
    db: AsyncSession, session_id: str, take: IRTake
) -> None:
    if take.id not in {part.id for part in current_parts(await takes_of(db, session_id))}:
        raise StretchNoLongerCounts("This recording is no longer one of the session's parts")


async def refuse_a_join_over_a_moved_part(
    db: AsyncSession, session_id: str, *, ordinal: int | None, over_take: str | None, audio: bytes
) -> None:
    """Refuse a join when its part's live take is not the one the team chose it over.

    `over_take` is that take, or None when the team chose the join over an empty scene. A join
    whose bytes are already kept is its own resend, answered by the storing with that take.
    """
    if await the_take_already_kept(db, session_id, IRTakeKind.ENSAIO, audio) is not None:
        return
    live = next(
        (p.id for p in current_parts(await takes_of(db, session_id)) if p.ordinal == ordinal),
        None,
    )
    if live != over_take:
        raise TakeMoved("This part's live take is no longer the one the join was chosen over")


def has_its_own_recording_time(spliced: Collection[str] = ()) -> ColumnElement[bool]:
    """Whether a take's `recorded_at` is its own **Recording time**, read off what every server
    that ever wrote a take stores, so a take written before this rule reads the same.

    A joined part names its `origin`. A tablet's time is never its arrival, which the server
    stamps from one clock reading for a take sent with none. A spliced part is stamped like a
    take sent with none, so the row cannot say it; the sentence laid into it can, and `spliced`
    is the takes that sentence makes one (`_spliced_into_a_timed_part`).
    """
    own = or_(IRTake.origin.is_not(None), IRTake.recorded_at != IRTake.created_at)
    return or_(own, IRTake.id.in_(spliced)) if spliced else own


def reading_order(spliced: Collection[str] = ()) -> tuple[UnaryExpression[Any], ...]:
    return (
        IRTake.ordinal.asc().nulls_first(),
        case((has_its_own_recording_time(spliced), IRTake.recorded_at), else_=None)
        .asc()
        .nulls_first(),
        IRTake.pass_number.asc().nulls_first(),
        IRTake.created_at.asc(),
    )


READING_ORDER = reading_order()


async def _spliced_into_a_timed_part(db: AsyncSession, session_id: str) -> set[str]:
    """The spliced parts of a session whose part had its own **Recording time**.

    Each sentence laid in names the take it was laid into, and every server that ever spliced
    wrote that, so this is read the same for a splice made before the rule. Walked in the order
    the sentences were laid, so a sentence laid again over a splice inherits through it.
    """
    told = await db.scalar(select(IRSession.back_translation).where(IRSession.id == session_id))
    laid = [(one["previous_take_id"], one["take_id"]) for one in (told or {}).get("sentences", [])]
    if not laid:
        return set()
    timed = set(
        (
            await db.execute(
                select(IRTake.id).where(
                    IRTake.id.in_({previous for previous, _ in laid}),
                    has_its_own_recording_time(),
                )
            )
        ).scalars()
    )
    spliced: set[str] = set()
    for previous, take_id in laid:
        if previous in timed or previous in spliced:
            spliced.add(take_id)
    return spliced


async def takes_of(db: AsyncSession, session_id: str) -> list[IRTake]:
    """Every take of a session, in reading order rather than in arrival order.

    A retry lands after a later stretch, so the created-at order alone puts the takes in
    the wrong sequence for whoever reviews the session.

    Under one ordinal the take recorded last reads last, by its **Recording time**, and the
    pass then the arrival break a tie. A take with no Recording time of its own — sent with
    none, stored before ENG-1273 and not joined, or spliced into a part like it — reads before
    every take that has one, and among its kind by the pass, which is the order it was read
    in before.

    Every key but the arrival is nullable, and its placement is named rather than left to the
    engine: a take with no ordinal belongs to no stretch — the undivided passage, or a
    recording that captured none — a take with no pass predates the room sending one, and a
    take with no Recording time of its own has nothing to be compared by, so each is the
    earliest thing in its own group. Unnamed, SQLite read that the same way and PostgreSQL read
    it upside down, which put the oldest recording of a session at the bottom of the packet on
    the only database that serves a real team.
    """
    spliced = await _spliced_into_a_timed_part(db, session_id)
    result = await db.execute(
        select(IRTake).where(IRTake.session_id == session_id).order_by(*reading_order(spliced))
    )
    return list(result.scalars().all())


def current_parts(takes: list[IRTake]) -> list[IRTake]:
    """The rehearsal takes that *are* the session's parts: the newest under each number.

    A **Part** is one rehearsal take of the passage, and its identity is the number the tablet
    sent with it — never the scope string, which the text seam writes as the pericope for every
    part it declares. Recording a part again stores a second take under that number; the newest
    of them is the part, and the earlier ones stay as history, which the **Retroverification
    file** is where anybody reads.

    A take with no number is the rehearsal told whole, which is one part of its own — but only
    while the session holds no numbered part. Once the team has recorded by scene the whole is
    history, kept with its stretches and findings and no longer a part anybody is asked for.

    **The newest is the last of its number in the order it was given**, which is `takes_of`'s:
    the one recorded last by its **Recording time**, with the pass breaking a tie. Keyed on the
    arrival it would be wrong: the outbox drains whenever the link comes back, so the rehearsal
    that arrives last is sometimes the one the team abandoned, and the Recording time does not
    move with the link. Keyed on the pass it would be wrong too: a reinstalled tablet, or a
    second one, counts its passes from 1 again, so its newer take would read below an older
    pass 2. A take with no Recording time of its own keeps the pass order and reads first.

    So this must be handed the list in that order — `takes_of`'s — and it answers in it, so the
    parts come back in the reading order and no caller sorts them again.
    """
    newest: dict[int | None, IRTake] = {}
    for take in takes:
        if take.kind is IRTakeKind.ENSAIO:
            newest[take.ordinal] = take
    if any(ordinal is not None for ordinal in newest):
        newest.pop(None, None)
    chosen = {take.id for take in newest.values()}
    return [take for take in takes if take.id in chosen]


def part_positions(parts: list[IRTake]) -> dict[int | None, int | None]:
    """Each current part's position among the session's current parts, by the number it carries.

    The number the voice says and the **Part key** are both read off this: a rehearsal told
    whole has no position, and the others count from one in reading order.
    """
    positions: dict[int | None, int | None] = {}
    counted = 0
    for part in parts:
        if part.ordinal is None:
            positions[None] = None
        else:
            counted += 1
            positions[part.ordinal] = counted
    return positions


def part_keys(parts: list[IRTake]) -> dict[str, str]:
    """Each current part's **Part key** by its take id: `whole`, or `S<n>` at position n."""
    positions = part_positions(parts)
    return {
        part.id: "whole" if positions[part.ordinal] is None else f"S{positions[part.ordinal]}"
        for part in parts
    }


#: Where a declared part's key lives, and the device a text seam speaks for. A part declared
#: through the seam has no bytes and no bucket object: it is the address a stretch is a slice
#: of, and nothing else, so the key carries the name her script gave it.
TEXT_SEAM_PREFIX = "text-seam"
TEXT_SEAM_DEVICE = "text-seam"
TEXT_SEAM_CONTENT_TYPE = "text/plain"


def is_declared(take: IRTake) -> bool:
    """A part the text seam declared: an address with no bytes and no bucket object."""
    return take.storage_key.startswith(f"{TEXT_SEAM_PREFIX}/")


def _declared_key(session_id: str, key: str) -> str:
    return f"{TEXT_SEAM_PREFIX}/{session_id}/{key}"


async def declare_rehearsal_parts(
    db: AsyncSession,
    session: IRSession,
    keys: list[str],
    content_types: Mapping[str, str] | None = None,
) -> list[IRTake]:
    """Her draft clips as real rehearsal takes, declared rather than uploaded.

    A **Part** the room can address is a row, not a file: `current_stretch_at`,
    `report_playback` and `unheard_parts` all read the row and the report, and none of them
    opens the audio. So the seam writes the row and stores nothing — the bucket is never
    touched, and the size and checksums say what they are, which is that there are no bytes
    to describe.

    `store_take` is deliberately not reused: it exists to put bytes somewhere and read them
    back, and it refuses a take with no audio. What they share is the row, and the row is
    written here.

    Only the keys: a declared part's length is not a column of a take, it is what the listening
    report says about it, and that is where her `durationMs` lands.
    """
    declared = [
        IRTake(
            id=str(uuid.uuid4()),
            project_id=session.project_id,
            session_id=session.id,
            device_id=TEXT_SEAM_DEVICE,
            pericope=session.pericope,
            kind=IRTakeKind.ENSAIO,
            scope=session.pericope,
            storage_key=_declared_key(session.id, key),
            size_bytes=0,
            sha256="",
            crc32c="",
            content_type=(content_types or {}).get(key, TEXT_SEAM_CONTENT_TYPE),
            ordinal=position,
        )
        for position, key in enumerate(keys)
    ]
    db.add_all(declared)
    await db.commit()
    for take in declared:
        await db.refresh(take)
    return declared


async def declared_parts_by_key(db: AsyncSession, session_id: str) -> dict[str, IRTake]:
    """The parts a seam session declared, by the key her script names them with."""
    prefix = _declared_key(session_id, "")
    result = await db.execute(
        select(IRTake).where(IRTake.session_id == session_id, IRTake.kind == IRTakeKind.ENSAIO)
    )
    return {
        take.storage_key.removeprefix(prefix): take
        for take in result.scalars()
        if is_declared(take)
    }
