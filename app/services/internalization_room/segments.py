"""Which stretches of a session count, and in what order.

One rule lives here and nowhere else: **what the room reads is the current leaf**. Current,
because a stretch can be replaced and the replaced one must never come back into the reading
by accident; leaf, because a stretch that was divided stops being a unit in favour of what it
was divided into. Every caller downstream — the analyst's prompt, the release artifact, the
state a tablet resumes from — asks `final_segments` and repeats none of it.

A told stretch's take is numbered here too, with the ordinal the stretch is given the moment
it is captured.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.db.models.internalization_room import IRSegment, IRSession, IRTake


def sits_at(segment: IRSegment, take_id: str, starts_ms: int, ends_ms: int) -> bool:
    """Whether this slice is where the stretch sits: the same recording, the same milliseconds.

    A stretch is addressed relative to one file (ADR 0005), so all three have to match for the
    slice to be the stretch's own. The one expression of it, asked by the refusal below and by
    the route that resolves a chunk against the stretch already standing at it.
    """
    return (
        segment.take_id == take_id and segment.starts_ms == starts_ms and segment.ends_ms == ends_ms
    )


def refuse_a_slice_the_stretch_does_not_sit_on(
    segment: IRSegment, take_id: str, starts_ms: int, ends_ms: int
) -> None:
    """A version of a stretch sits where that stretch sits.

    A **Correction** is the same stretch told again over the recording it already sits in, so a
    version naming other audio would be a version of somebody else's seconds under this
    stretch's id. A team whose *recording* is wrong records the **Part** again, which is an
    upload under that part's number (ADR 0023) and retires that part's stretches; it never
    arrives here.

    The message names the two slices and nothing else. What stood here before refused a moved
    slice only when a telling came with it, and said so by naming the product's two kinds of
    correction; a team reading that has no way to act on it — where the audio is, they can hear.

    One expression, called from the invariant below and from the route that replaces a stretch,
    where it runs before any bytes are kept: the combination is knowable from the stretch and
    the form fields, so nothing is spent on a request that cannot succeed.
    """
    if not sits_at(segment, take_id, starts_ms, ends_ms):
        raise ValidationError(
            f"The slice from {starts_ms} ms to {ends_ms} ms of {take_id} is not this stretch's: "
            f"it sits from {segment.starts_ms} ms to {segment.ends_ms} ms of {segment.take_id}"
        )


def refuse_a_version_that_tells_nothing(transcript: str | None) -> None:
    """A **Correction** is a telling, so a version of a stretch arrives with words.

    A version with none said nothing into the stretch it replaces: it would stand in its place
    carrying the audio it already had and no telling at all, which is the stretch going
    backwards. The state existed to describe the mother tongue re-recorded, and that is answered
    by recording the **Part** again (ADR 0023, ADR 0025).

    Refused rather than defaulted. A default is overridden by the next caller who has no words
    in hand and no reason to think twice; a refusal is what makes the state unreachable. What
    leaves a stretch waiting to be told is the team cutting one in two, where each piece is born
    with nothing said on it and `parent` says so.
    """
    if transcript is None:
        raise ValidationError(
            "A version of a stretch is the stretch told again, so it arrives with a telling: "
            "this one carries none"
        )


def refuse_a_slice_that_is_not_one(starts_ms: int, ends_ms: int) -> None:
    """A stretch has to be a piece of audio somebody can hear.

    An end before the beginning is not an interval, and an end on the beginning is no audio at
    all. Both were accepted in silence and became final units — and a unit with no audio can
    never be told back, so it can never be completed, so the first round waits on it for good.
    The same argument that makes a cut on the border a refusal, arriving at the same place from
    the other side.

    One expression, called from the invariant below and from the route that tells a stretch
    back, where it runs before any bytes are kept: a malformed slice is the app's own bug and
    retrying costs the team nothing, unlike a transcriber that went away mid-request.
    """
    if ends_ms <= starts_ms:
        raise ValidationError(
            f"A stretch from {starts_ms} ms to {ends_ms} ms is not a slice of anything"
        )


async def capture_segment(
    db: AsyncSession,
    session: IRSession,
    *,
    take_id: str,
    starts_ms: int,
    ends_ms: int,
    bridge_take_id: str | None = None,
    transcript: str | None = None,
    pass_number: int = 1,
    parent: IRSegment | None = None,
    replaces: IRSegment | None = None,
    commit: bool = True,
) -> IRSegment:
    """Write one stretch: the slice of a recording, and what the team told back about it.

    ``parent`` makes it a stretch divided out of another, which stops the other counting as a
    final unit. ``replaces`` makes it a new version of one position: the earlier row stops
    counting and names this one as what took its place, and stays exactly where it is.

    **The count of tellings follows the chain, and a version is always one more.** Every version
    carries a telling — `refuse_a_version_that_tells_nothing` — so there is no supersession with
    nothing said into it to carry the count across untouched. The pieces of a division keep the
    count for the reason they keep the pass: born on the default, a stretch already told twice
    would hand the team a fresh count on each piece.

    **A version keeps the slice of the stretch it replaces**:
    `refuse_a_slice_the_stretch_does_not_sit_on`. A stretch is one slice of one recording, so a
    version naming other audio is not another telling of it. The recording the team performed
    is the one that travels (ADR 0025), and a recording that was wrong is answered by recording
    the **Part** again, which is an upload and not a version.

    What may be replaced at all — not a retired row, not one the team divided — is
    `refuse_a_stretch_that_is_not_a_unit`, which the route that counts an unheard telling asks
    the same question of.

    The retired row is stamped before the successor is inserted, not after. The two share a
    position, and the index that keeps one position to one current stretch is checked per
    statement — inserting first would put both of them under it at once.

    ``commit=False`` leaves the transaction open so a caller can write more in it. The telling
    that crosses into a hard stretch is what needs it: the row, the telling-back state and the
    mark are one fact, and this row committed on its own leaves a stretch standing at the
    number with no mark when the halt after it fails.
    """
    refuse_a_slice_that_is_not_one(starts_ms, ends_ms)

    if replaces is not None:
        refuse_a_slice_the_stretch_does_not_sit_on(replaces, take_id, starts_ms, ends_ms)
        refuse_a_version_that_tells_nothing(transcript)
        await refuse_a_stretch_that_is_not_a_unit(db, session.id, replaces)
        parent_id = replaces.parent_id
        ordinal = replaces.ordinal
        tellings = replaces.tellings + 1
    elif parent is not None:
        parent_id = parent.id
        ordinal = await _next_ordinal(db, session.id, parent_id)
        tellings = parent.tellings
    else:
        parent_id = None
        ordinal = await _next_ordinal(db, session.id, parent_id)
        tellings = 1

    if bridge_take_id is not None:
        result = await db.execute(
            select(IRTake).where(IRTake.id == bridge_take_id, IRTake.session_id == session.id)
        )
        bridge_take = result.scalar_one_or_none()
        if bridge_take is not None:
            bridge_take.ordinal = ordinal

    segment_id = str(uuid.uuid4())
    if replaces is not None:
        replaces.superseded_at = datetime.now(UTC)
        replaces.superseded_by_id = segment_id
        await db.flush()

    segment = IRSegment(
        id=segment_id,
        session_id=session.id,
        project_id=session.project_id,
        parent_id=parent_id,
        ordinal=ordinal,
        take_id=take_id,
        starts_ms=starts_ms,
        ends_ms=ends_ms,
        pass_number=pass_number,
        tellings=tellings,
        bridge_take_id=bridge_take_id,
        transcript=transcript,
    )
    db.add(segment)
    if commit:
        await db.commit()
        await db.refresh(segment)
    else:
        await db.flush()
    return segment


async def divide_segment(
    db: AsyncSession, session: IRSession, segment: IRSegment, *, at_ms: int
) -> list[IRSegment]:
    """Cut one stretch in two at a point the team chose, and answer with the pieces.

    ``at_ms`` is in the same coordinates as ``starts_ms`` and ``ends_ms`` — milliseconds from
    the start of **that recording**, never an offset into the stretch. A number that only means
    something with another number beside it is the global timeline under a new name, which is
    the defect the segment was introduced to remove.

    The pieces are ``[starts_ms, at_ms)`` and ``[at_ms, ends_ms)``. Half-open, so the
    millisecond of the cut belongs to the **second** piece and the two tile the original
    exactly: closed on both sides would count that millisecond twice, open on both would drop
    it. It is also how the room already writes consecutive stretches — one ends on the value
    the next begins on — so this is the reading that makes what exists correct rather than
    ambiguous. Anybody tempted to "fix" it to closed on both sides should read this first.

    **The cut must fall strictly inside**, and that is not tidiness. A cut on either border
    makes a piece of no duration, and a piece of no duration is a final unit that can never be
    completed: no audio to hear, so nothing to tell back, so no explanation, ever. The first
    round only releases when every final unit has one, so a tap a millisecond wide of the mark
    would jam the passage for good — and the team has no verb to undo it.

    There is deliberately **no minimum duration**. Any floor would be a number invented here
    rather than measured, the team picks the cut by tapping while they listen, and the room has
    no screen to explain a refusal with: a floor would arrive as a mute "no". Zero is refused
    because at zero the piece does not exist; every other bound would be policy.

    A stretch that was already divided is refused, for the reason its replacement is: its audio
    is covered by its pieces, and cutting it again would make a sibling overlapping its own
    nephews. So is one that no longer counts — dividing what does not count yields pieces
    nobody would ever see.

    The pieces keep the pass the stretch they came from was told on. Born on the default, a
    division of something the team had already been asked about once would have travelled to
    Refine looking like a first telling.
    """
    if segment.superseded_at is not None:
        raise ValidationError("A stretch that no longer counts cannot be divided")
    if any(row.parent_id == segment.id for row in await current_segments(db, session.id)):
        raise ValidationError(
            "This stretch was already divided: divide one of the stretches it was divided into"
        )
    if not segment.starts_ms < at_ms < segment.ends_ms:
        raise ValidationError(
            f"A cut at {at_ms} ms falls on or outside the stretch "
            f"({segment.starts_ms} to {segment.ends_ms} ms): it would make a piece with no audio"
        )

    head = await capture_segment(
        db,
        session,
        take_id=segment.take_id,
        starts_ms=segment.starts_ms,
        ends_ms=at_ms,
        pass_number=segment.pass_number,
        parent=segment,
    )
    tail = await capture_segment(
        db,
        session,
        take_id=segment.take_id,
        starts_ms=at_ms,
        ends_ms=segment.ends_ms,
        pass_number=segment.pass_number,
        parent=segment,
    )
    return [head, tail]


async def segment_for_session(db: AsyncSession, session_id: str, segment_id: str) -> IRSegment:
    """One stretch of **this** session, by its address.

    The room key is one string shipped in every tablet, so it says nothing about whose work is
    being reached; the session in the path is what does. Scoped here rather than by the caller,
    because a lookup that returns any stretch to anybody is a lookup every route has to
    remember to fence.

    One message for absent, for somebody else's and for never having existed, the way
    ``_no_such_session`` and ``_no_such_take`` already answer (ENG-534). It echoes back the id
    the caller sent, which tells them nothing they did not already know.
    """
    result = await db.execute(
        select(IRSegment).where(IRSegment.id == segment_id, IRSegment.session_id == session_id)
    )
    segment = result.scalar_one_or_none()
    if segment is None:
        raise NotFoundError(f"Internalization room segment {segment_id} not found")
    return segment


def _read_in_order(rows: list[IRSegment]) -> Iterator[tuple[IRSegment, bool]]:
    """Every stretch in the order the passage is read, each with whether it was divided.

    The walk the reading is: a stretch, then the stretches it was divided into, in the order
    the rows arrive — which `current_segments` has already put in the part's number and the
    milliseconds inside it. Written once because the two questions asked of it disagree about
    which rows they want and must never disagree about the order: the leaves are the reading,
    and the stretches that are not leaves are the ones the team cut in two.
    """
    children: dict[str | None, list[IRSegment]] = {}
    for row in rows:
        children.setdefault(row.parent_id, []).append(row)

    def walk(parent_id: str | None) -> Iterator[tuple[IRSegment, bool]]:
        for row in children.get(parent_id, []):
            divided = bool(children.get(row.id))
            yield row, divided
            if divided:
                yield from walk(row.id)

    yield from walk(None)


async def divided_segments(db: AsyncSession, session_id: str) -> list[IRSegment]:
    """The stretches that were divided: current, and no longer a leaf.

    They fall between the two lists the handoff used to carry — not final units, because they
    were divided, and not retired, because nothing replaced them. What the team said about the
    whole stretch, before they heard two ideas in it, vanished from the artifact in silence.

    The same class of loss as a replaced stretch, which the handoff carries on purpose. The
    verb that creates the state is what has to carry it.

    In the order the reading walks them, so a stretch comes before the pieces it was cut into.
    A piece is numbered among its own siblings and not over the passage, so in row order a
    piece of a later part sorted ahead of the stretch it came out of — and a reader of the list
    met the child before its own parent.
    """
    rows = await current_segments(db, session_id)
    return [row for row, divided in _read_in_order(rows) if divided]


async def final_segments(db: AsyncSession, session_id: str) -> list[IRSegment]:
    """The stretches that count, in the order the team told them.

    Current and leaf, which is the whole selection rule of the room in one place. Where a
    stretch reads is where its audio sits — the part it is a slice of, then the milliseconds
    inside that part — so a stretch written long after its neighbours still reads in its own
    place, and a replacement reads where the row it replaced did. `current_segments` is where
    that order is asked of the database; the hierarchy is walked here, because a stretch the
    team divided is read as its pieces and the walk is the same on both databases.
    """
    rows = await current_segments(db, session_id)
    return [row for row, divided in _read_in_order(rows) if not divided]


def told_back(segments: list[IRSegment]) -> list[IRSegment]:
    """Of those stretches, the ones the team has actually explained in the bridge language.

    A piece the team cut out of another stretch is a real unit and the tablet has to see it,
    but it carries nothing the team said — and nothing is not a text. It reached the analyst as
    a literal ``None``, a line nobody uttered, which the analyst then compared against the map
    and could raise a finding on.

    Kept separate from `final_segments` because the two questions are different: which
    stretches count, and which of them are evidence. Both the numbering the analyst is given
    and the reading of its answer come from this one list, so they cannot drift apart.
    """
    return [segment for segment in segments if segment.transcript is not None]


def first_untold(segments: list[IRSegment]) -> IRSegment | None:
    """The earliest stretch that counts and carries no telling-back, or nothing if none does.

    The complement of `told_back` over the same list, and it lives beside it for the same
    reason the two are one function apart: which stretches count, and which of them are
    evidence, are answered in one place so the count that stops the analyst and the address
    the team is sent to cannot disagree.

    Earliest, because a team tells a passage in its own sequence: sent to a hole in the
    middle while an earlier one is still open, they work backwards through their own
    recording. Earliest by position, which is not the same as earliest in the take — a
    stretch re-recorded against a different slice keeps the position it had.

    The caller decides which stretches are in scope, and none of the selection rules are
    repeated here: `finish` passes `final_segments`, so what is walked is already current
    and already in the order the team told in.
    """
    return next((segment for segment in segments if segment.transcript is None), None)


async def retired_segments(db: AsyncSession, session_id: str) -> list[IRSegment]:
    """The stretches that stopped counting, oldest first.

    Kept rather than erased: a replaced stretch is the history the Refine artifact carries, and
    a team's open question has to survive their own retake.
    """
    result = await db.execute(
        select(IRSegment)
        .where(IRSegment.session_id == session_id, IRSegment.superseded_at.is_not(None))
        .order_by(IRSegment.superseded_at, IRSegment.created_at)
    )
    return list(result.scalars().all())


async def segment_by_id(db: AsyncSession, segment_id: str) -> IRSegment:
    """One stretch by its own address, whether it still counts or not."""
    result = await db.execute(select(IRSegment).where(IRSegment.id == segment_id))
    segment = result.scalar_one_or_none()
    if segment is None:
        raise NotFoundError(f"Internalization room segment {segment_id} not found")
    return segment


async def parent_of(db: AsyncSession, segment: IRSegment) -> IRSegment | None:
    """The stretch this one was divided out of, or None when nobody divided it."""
    if segment.parent_id is None:
        return None
    return await segment_by_id(db, segment.parent_id)


def _stop_counting(segments: list[IRSegment]) -> None:
    """Stamp one moment on every one of them, with nothing taking their place.

    What stops a stretch counting and what replaced it are two separate facts, and here there
    is no successor to name: these are **Abandoned** rows. One moment for the lot, because it
    is one act.
    """
    at = datetime.now(UTC)
    for segment in segments:
        segment.superseded_at = at


async def retire_every_segment(db: AsyncSession, session_id: str) -> None:
    """Stop every current stretch of a session counting.

    This is a telling-back started over on a recording the team threw away: the whole rehearsal
    went, so the whole reading goes with it.
    """
    _stop_counting(await current_segments(db, session_id))
    await db.commit()


async def retire_the_segments_of(
    db: AsyncSession, session_id: str, *, take_ids: set[str]
) -> list[IRSegment]:
    """Stop the stretches of these recordings counting, and answer with which ones went.

    Recording one **Part** again is the narrow case of the verb above: what goes is the
    stretches that are slices of the takes the new one replaces, and what stands is every other
    part. The caller needs to know which rows went, because the findings that pointed at them go
    too.

    **A piece of a stretch that goes is a piece of that part**, and the walk down the children
    is what says so rather than the take each piece carries. Taken by the take alone, a piece
    could outlive its own parent: a row still counting whose parent is abandoned, which the
    reading walks from the top and never reaches, so it would vanish from the packet, the check
    block, the analyst's list and the listening gate while the row went on saying it counts.
    A version now keeps the slice of the stretch it replaces (ADR 0025), so a row written from
    here on sits on its parent's take and the two readings agree. The walk stays because the
    rows ADR 0023 tolerates as history do not: one written while a version could move onto
    another recording still sits there, and its part is the one it was cut from.

    The transaction is left open, because the retired rows and the telling-back state they empty
    are one fact about one upload: committed apart, a failure between them leaves the room
    carrying findings about audio nobody will hear again.
    """
    rows = await current_segments(db, session_id)
    children: dict[str | None, list[IRSegment]] = {}
    for row in rows:
        children.setdefault(row.parent_id, []).append(row)

    leaving = {row.id for row in rows if row.take_id in take_ids}
    walking = [row for row in rows if row.id in leaving]
    while walking:
        for piece in children.get(walking.pop().id, []):
            if piece.id not in leaving:
                leaving.add(piece.id)
                walking.append(piece)

    going = [row for row in rows if row.id in leaving]
    if not going:
        return going
    _stop_counting(going)
    await db.flush()
    return going


async def current_segments(db: AsyncSession, session_id: str) -> list[IRSegment]:
    """Every stretch of a session that still counts, divided ones included, in reading order.

    One step short of `final_segments`, which keeps only the leaves. What wants this rather
    than that is what is about the rows and not about the reading: the ordinal a new stretch
    takes, and the re-addressing of a passage that was rebuilt, where a stretch the team
    divided has to move with its own children or stop describing them.

    **The order is the part's number, then the milliseconds inside it** (ADR 0021). The stretch
    ordinal is one past the last of its own current siblings, which held while the only way to
    retire a stretch was to retire every one of them at once; recording one **Part** again
    retires that part alone, and the telling that follows took the next free number and read
    after every part later in the passage.

    The join is outer because a stretch names a take across an app boundary and nothing at the
    database level says the row is there (ADR 0006). `nulls_first` is named rather than left to
    the engine, for the reason `takes_of` says it: SQLite sorts a NULL first and PostgreSQL
    last, and the whole recording — the part with no number — reads before the numbered ones.
    """
    result = await db.execute(
        select(IRSegment)
        .outerjoin(IRTake, IRSegment.take_id == IRTake.id)
        .where(IRSegment.session_id == session_id, IRSegment.superseded_at.is_(None))
        .order_by(
            IRTake.ordinal.asc().nulls_first(),
            IRSegment.starts_ms,
            IRSegment.ordinal,
            IRSegment.created_at,
        )
    )
    return list(result.scalars().all())


async def _next_ordinal(db: AsyncSession, session_id: str, parent_id: str | None) -> int:
    """One past the last of its own siblings.

    Counted over the current ones only, so a session whose telling-back was started over
    numbers the new stretches from the beginning again. Ordinals order; they do not need to
    be dense.
    """
    siblings = [row for row in await current_segments(db, session_id) if row.parent_id == parent_id]
    return max((row.ordinal for row in siblings), default=0) + 1


async def first_telling_of(db: AsyncSession, segment: IRSegment) -> IRSegment:
    """Walk back up the chain of replacements to the row the team told first.

    The chain the rows carry runs forward — a retired row names what took its place — so the
    walk is a query per hop. Chains are the number of times one stretch was told, which is small
    by the nature of the thing: a stretch told enough times to make this walk long is the stretch
    this whole count exists to notice.
    """
    first = segment
    while True:
        result = await db.execute(
            select(IRSegment).where(
                IRSegment.session_id == segment.session_id,
                IRSegment.superseded_by_id == first.id,
            )
        )
        earlier = result.scalar_one_or_none()
        if earlier is None:
            return first
        first = earlier


async def current_stretch_at(
    db: AsyncSession, session_id: str, *, take_id: str, starts_ms: int, ends_ms: int
) -> IRSegment | None:
    """The stretch that counts at exactly this slice, or nothing when none does.

    How the telling-back route knows a chunk is one more telling of a stretch already told
    rather than a stretch nobody has told yet: the tablet sends the stretch's own address back.

    Read off the leaves, which is what the room reads. A stretch that was divided is no longer
    a unit — its audio belongs to its pieces — so a chunk over its old slice is a stretch of its
    own, and replacing it is refused anyway.
    """
    return next(
        (
            segment
            for segment in await final_segments(db, session_id)
            if sits_at(segment, take_id, starts_ms, ends_ms)
        ),
        None,
    )


async def refuse_a_stretch_that_is_not_a_unit(
    db: AsyncSession, session_id: str, segment: IRSegment
) -> None:
    """A stretch that no longer counts, or that was divided, is not a stretch to act on.

    **A stretch that no longer counts cannot be replaced.** A tablet retrying a replacement it
    already sent lands on the row it superseded: the successor would take a position another
    current row already holds, which the index refuses with a 500 nobody in the room can read —
    and once a telling-back has been started over there is no current row left to collide with,
    so the same call would quietly bring a stretch back from the recording the team threw away.

    **A stretch that was divided cannot be replaced as a unit.** Its children would go on
    pointing at the retired row, which the walk in `final_segments` starts too high up to
    reach, and they would drop out of the reading with nothing saying so. It is refused rather
    than repaired because the parent stopped being a unit the moment it was divided: what gets
    re-recorded is a child, one at a time.

    One expression, because the two callers must answer the same. `capture_segment` asks it
    before writing a replacement; the correction route asks it before *counting* on a row,
    where an unguarded retry used to spend a telling on a stretch the room had already retired
    and could mark a divided parent nothing can ever replace.
    """
    if segment.superseded_at is not None:
        raise ValidationError(
            "This stretch no longer counts: it was already replaced, or the telling-back "
            "it belonged to was started over"
        )
    if any(row.parent_id == segment.id for row in await current_segments(db, session_id)):
        raise ValidationError(
            "A stretch that was divided is no longer a unit: replace one of the stretches "
            "it was divided into, not the stretch itself"
        )
