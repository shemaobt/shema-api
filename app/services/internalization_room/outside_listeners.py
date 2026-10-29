"""The **Outside listeners** of a **Checagem externa** and every recording they make (ADR 0083).

A listener is the next number of the check's version and nothing that names a person. Each
**Listener recording** is in the bucket before its row names it. Nothing here hears: no
recognizer and no model is imported, and none may be (the app's ADR 0111).
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.db.models.internalization_room import (
    IRExternalCheck,
    IRExternalListener,
    IRExternalMark,
    IRExternalRecording,
    IRExternalRecordingKind,
    IRRelease,
    IRSession,
)
from app.models.internalization_room import (
    ExternalCheckPointer,
    ListenerFacts,
    ListenerFactsFrase,
    ListenerFraseView,
    ListenerRecordingView,
    ListenerView,
)
from app.services.internalization_room.takes import (
    TakeStore,
    checked_recording,
    extension,
    store_recording,
)
from app.utils.stored_time import as_utc

#: The house loop's bound (``scene_rehearsals.NUMBERING_TRIES``), not imported from there
#: because that module hears, and this one may not reach anything that does.
NUMBERING_TRIES = 50

#: Where the facilitator reads a version's listeners, which the manifest points to.
EXTERNAL_CHECK_ROUTE = (
    "/api/internalization-room/facilitator/sessions/{session_id}/external-check/{version}"
)


async def the_check_of_version(
    db: AsyncSession, session: IRSession, version: int
) -> IRExternalCheck:
    """The check the team opened for this version, writable as long as it exists: a draft
    re-opened after it leaves it as it was (her spec §1, "the version does the work")."""
    check: IRExternalCheck | None = await db.scalar(
        select(IRExternalCheck).where(
            IRExternalCheck.session_id == session.id, IRExternalCheck.version == version
        )
    )
    if check is None:
        raise NotFoundError(f"No external check of version {version} in session {session.id}")
    return check


async def _held_archive(
    db: AsyncSession, parent: type[IRExternalCheck] | type[IRExternalListener], parent_id: str
) -> str | None:
    """The parent row's **Archive**, read under its lock and held to the commit: a Zerar that
    committed first is seen and copied, and one that comes after waits for the row and then
    stamps what was written under it, the way a scene frase takes its rehearsal's."""
    archive_id: str | None = await db.scalar(
        select(parent.archive_id).where(parent.id == parent_id).with_for_update()
    )
    return archive_id


async def _last_number(db: AsyncSession, check_id: str) -> int:
    last = await db.scalar(
        select(func.max(IRExternalListener.number)).where(IRExternalListener.check_id == check_id)
    )
    return int(last or 0)


async def _the_same_tap(db: AsyncSession, check_id: str, attempt: str) -> IRExternalListener | None:
    found: IRExternalListener | None = await db.scalar(
        select(IRExternalListener).where(
            IRExternalListener.check_id == check_id, IRExternalListener.attempt == attempt
        )
    )
    return found


async def a_new_listener(
    db: AsyncSession, check: IRExternalCheck, *, attempt: str
) -> IRExternalListener:
    """The next number of the check's version, or the listener this tap already minted.

    Two tablets asking at once can read the same last number: the unique index refuses the
    second, which walks to the next one. A tap sent again after its answer was lost carries the
    same attempt and is the same listener, whether it comes after the first landed or meets it
    at the index.
    """
    check_id, session_id = check.id, check.session_id
    already = await _the_same_tap(db, check_id, attempt)
    if already is not None:
        return already
    archive_id = await _held_archive(db, IRExternalCheck, check_id)
    last = await _last_number(db, check_id)
    for number in range(last + 1, last + 1 + NUMBERING_TRIES):
        listener = IRExternalListener(
            check_id=check_id,
            session_id=session_id,
            number=number,
            attempt=attempt,
            archive_id=archive_id,
        )
        try:
            async with db.begin_nested():
                db.add(listener)
        except IntegrityError:
            winner = await _the_same_tap(db, check_id, attempt)
            if winner is not None:
                return winner
            continue
        await db.commit()
        return listener
    raise ConflictError(f"Could not number an outside listener of check {check_id}")


async def the_listener(db: AsyncSession, check: IRExternalCheck, number: int) -> IRExternalListener:
    listener: IRExternalListener | None = await db.scalar(
        select(IRExternalListener).where(
            IRExternalListener.check_id == check.id, IRExternalListener.number == number
        )
    )
    if listener is None:
        raise NotFoundError(f"No outside listener {number} in check {check.id}")
    return listener


def listening_units(check: IRExternalCheck) -> list[str]:
    """What a listener comments on or marks, in the check's order: its stretches by
    ``segment_id``, or, on a check with nothing told, its parts by ``take_id`` (her
    ``unit: "take"``)."""
    if check.frases:
        return [frase["segment_id"] for frase in check.frases]
    return [take["take_id"] for take in check.takes]


def _a_unit_of(check: IRExternalCheck, segment_id: str | None) -> str:
    if segment_id is None or segment_id not in listening_units(check):
        raise ValidationError(f"{segment_id!r} is not a frase of version {check.version}")
    return segment_id


def _kind(check: IRExternalCheck, kind: str, segment_id: str | None) -> IRExternalRecordingKind:
    try:
        known = IRExternalRecordingKind(kind)
    except ValueError:
        raise ValidationError(f"Unknown recording kind: {kind!r}") from None
    if known is IRExternalRecordingKind.FRASE:
        _a_unit_of(check, segment_id)
    elif segment_id is not None:
        raise ValidationError(f"A {kind} recording is on no frase")
    return known


async def _the_same_recording(
    db: AsyncSession, listener_id: str, sha256: str
) -> IRExternalRecording | None:
    found: IRExternalRecording | None = await db.scalar(
        select(IRExternalRecording).where(
            IRExternalRecording.listener_id == listener_id, IRExternalRecording.sha256 == sha256
        )
    )
    return found


async def keep_a_listener_recording(
    db: AsyncSession,
    check: IRExternalCheck,
    listener: IRExternalListener,
    *,
    kind: str,
    segment_id: str | None,
    audio: bytes,
    content_type: str,
    sent_sha256: str | None,
    sent_duration_ms: int | None,
    store: TakeStore | None = None,
) -> IRExternalRecording:
    """Store the bytes, then attach them: a recording that dies in the upload leaves no row.

    The row takes its listener's **Archive** under the listener's lock once the bytes are safe,
    so a Zerar that lands during the upload stamps it too, and the bucket is never waited on
    with the row held.

    The same bytes sent again by this listener are the recording already kept, whether the
    resend comes after the first landed or meets it at the unique index.
    """
    known = _kind(check, kind, segment_id)
    checked = await checked_recording(
        audio, sent_sha256=sent_sha256, sent_duration_ms=sent_duration_ms
    )
    listener_id = listener.id
    already = await _the_same_recording(db, listener_id, checked.sha256)
    if already is not None:
        return already
    recording_id = str(uuid.uuid4())
    key = (
        f"internalization-room/external/{check.release_id}/{listener.number}/"
        f"{recording_id}.{extension(content_type)}"
    )
    check_id, session_id = check.id, check.session_id
    await db.commit()

    stored = await store_recording(
        audio, key=key, sha256=checked.sha256, content_type=content_type, store=store
    )
    recording = IRExternalRecording(
        id=recording_id,
        listener_id=listener_id,
        check_id=check_id,
        session_id=session_id,
        kind=known,
        segment_id=segment_id,
        storage_key=stored.storage_key,
        content_type=stored.content_type,
        duration_ms=checked.duration_ms,
        size_bytes=stored.size_bytes,
        sha256=stored.sha256,
        crc32c=stored.crc32c,
        verified_at=stored.verified_at,
        archive_id=await _held_archive(db, IRExternalListener, listener_id),
    )
    try:
        async with db.begin_nested():
            db.add(recording)
    except IntegrityError:
        winner = await _the_same_recording(db, listener_id, checked.sha256)
        if winner is None:
            raise
        return winner
    await db.commit()
    return recording


async def mark_the_frase_good(
    db: AsyncSession, check: IRExternalCheck, listener: IRExternalListener, segment_id: str
) -> None:
    """«Está boa» on one frase; marking it again is the same mark."""
    mark = IRExternalMark(
        listener_id=listener.id,
        session_id=listener.session_id,
        segment_id=_a_unit_of(check, segment_id),
        archive_id=await _held_archive(db, IRExternalListener, listener.id),
    )
    try:
        async with db.begin_nested():
            db.add(mark)
    except IntegrityError:
        return
    await db.commit()


async def finish_the_listener(
    db: AsyncSession, listener: IRExternalListener, *, completed: bool
) -> None:
    """The first finish is how the listener ended; a resend with another value, or one landing
    at once, changes nothing."""
    await db.execute(
        update(IRExternalListener)
        .where(IRExternalListener.id == listener.id, IRExternalListener.finished_at.is_(None))
        .values(finished_at=datetime.now(UTC), completed=completed)
    )
    await db.commit()


async def the_listeners_of(
    db: AsyncSession, check: IRExternalCheck, *, number: int | None = None
) -> list[ListenerView]:
    """Every listener of the check in number order, or the one numbered, as they stand.

    The newest retelling is the listener's retelling, the earlier ones stay stored. A frase has
    an entry only once it was marked or commented, ok only when marked with no comment (her
    ``applyMark``/``applyClip``): a frase only heard reads "not answered", never "good".
    """
    chosen = select(IRExternalListener).where(IRExternalListener.check_id == check.id)
    if number is not None:
        chosen = chosen.where(IRExternalListener.number == number)
    listeners = list((await db.scalars(chosen.order_by(IRExternalListener.number))).all())
    ids = [listener.id for listener in listeners]
    recordings = (
        await db.scalars(
            select(IRExternalRecording)
            .where(IRExternalRecording.listener_id.in_(ids))
            .order_by(IRExternalRecording.stored_at, IRExternalRecording.id)
        )
    ).all()
    marks = (
        await db.execute(
            select(IRExternalMark.listener_id, IRExternalMark.segment_id).where(
                IRExternalMark.listener_id.in_(ids)
            )
        )
    ).all()
    numbers = _frase_numbers(check)
    kept: dict[str, list[IRExternalRecording]] = defaultdict(list)
    for recording in recordings:
        kept[recording.listener_id].append(recording)
    marked = {(listener_id, segment_id) for listener_id, segment_id in marks}
    return [
        _listener_view(check, listener, kept[listener.id], marked, numbers)
        for listener in listeners
    ]


async def a_listeners_facts(db: AsyncSession, check: IRExternalCheck, number: int) -> ListenerFacts:
    """What the team reads back of a listener: how many of each recording were kept and on
    which frases, and the marks; never a recording id, a fingerprint or a way to the audio."""
    heard = await the_listeners_of(db, check, number=number)
    if not heard:
        raise NotFoundError(f"No outside listener {number} in check {check.id}")
    (listener,) = heard
    return ListenerFacts(
        number=listener.number,
        started_at=listener.started_at,
        finished_at=listener.finished_at,
        completed=listener.completed,
        retold=listener.retelling is not None,
        whole=len(listener.whole),
        frases=[
            ListenerFactsFrase(
                segment_id=frase.segment_id,
                frase=frase.frase,
                ok=frase.ok,
                comments=len(frase.comments),
            )
            for frase in listener.frases
        ],
    )


def _listener_view(
    check: IRExternalCheck,
    listener: IRExternalListener,
    recordings: list[IRExternalRecording],
    marked: set[tuple[str, str]],
    numbers: dict[str, int | None],
) -> ListenerView:
    of_kind: dict[IRExternalRecordingKind, list[ListenerRecordingView]] = defaultdict(list)
    comments: dict[str | None, list[ListenerRecordingView]] = defaultdict(list)
    for recording in recordings:
        view = _recording_view(recording, numbers)
        of_kind[recording.kind].append(view)
        comments[recording.segment_id].append(view)
    retellings = of_kind[IRExternalRecordingKind.RETELL]
    return ListenerView(
        number=listener.number,
        started_at=as_utc(listener.started_at).isoformat(),
        finished_at=as_utc(listener.finished_at).isoformat() if listener.finished_at else None,
        completed=listener.completed,
        retelling=retellings[-1] if retellings else None,
        whole=of_kind[IRExternalRecordingKind.WHOLE],
        frases=[
            ListenerFraseView(
                segment_id=unit,
                frase=numbers.get(unit),
                ok=not comments[unit],
                comments=comments[unit],
            )
            for unit in listening_units(check)
            if (listener.id, unit) in marked or comments[unit]
        ],
    )


def _frase_numbers(check: IRExternalCheck) -> dict[str, int | None]:
    return {frase["segment_id"]: frase["frase"] for frase in check.frases}


def recording_view(check: IRExternalCheck, recording: IRExternalRecording) -> ListenerRecordingView:
    return _recording_view(recording, _frase_numbers(check))


def _recording_view(
    recording: IRExternalRecording, numbers: dict[str, int | None]
) -> ListenerRecordingView:
    return ListenerRecordingView(
        recording_id=recording.id,
        kind=recording.kind.value,
        segment_id=recording.segment_id,
        frase=numbers.get(recording.segment_id) if recording.segment_id else None,
        content_type=recording.content_type,
        duration_ms=recording.duration_ms,
        size_bytes=recording.size_bytes,
        sha256=recording.sha256,
        stored_at=as_utc(recording.stored_at).isoformat(),
    )


async def listeners_counted(db: AsyncSession, release: IRRelease) -> int:
    """How many outside listeners the check of this release has; none before it is opened."""
    counted = await db.scalar(
        select(func.count(IRExternalListener.id))
        .join(IRExternalCheck, IRExternalCheck.id == IRExternalListener.check_id)
        .where(IRExternalCheck.release_id == release.id)
    )
    return int(counted or 0)


async def comments_counted(db: AsyncSession, release: IRRelease) -> int:
    """How many whole-passage and frase comments this release's check holds, not the retelling."""
    counted = await db.scalar(
        select(func.count(IRExternalRecording.id))
        .join(IRExternalCheck, IRExternalCheck.id == IRExternalRecording.check_id)
        .where(
            IRExternalCheck.release_id == release.id,
            IRExternalRecording.kind.in_(
                (IRExternalRecordingKind.WHOLE, IRExternalRecordingKind.FRASE)
            ),
        )
    )
    return int(counted or 0)


async def external_check_pointer(
    db: AsyncSession, release: IRRelease
) -> ExternalCheckPointer | None:
    """Her ``externalCheck`` for a release: how many listened, how many commented, and the
    facilitator's read of them; none while the team has not opened the check."""
    check = await db.scalar(select(IRExternalCheck).where(IRExternalCheck.release_id == release.id))
    if check is None:
        return None
    return ExternalCheckPointer(
        listeners=await listeners_counted(db, release),
        comments=await comments_counted(db, release),
        url=EXTERNAL_CHECK_ROUTE.format(session_id=check.session_id, version=check.version),
    )
