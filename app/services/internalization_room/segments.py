"""Which stretches of a session count, and in what order.

One rule lives here and nowhere else: **what the room reads is the current leaf**. Current,
because a stretch can be replaced and the replaced one must never come back into the reading
by accident; leaf, because a stretch that was divided stops being a unit in favour of what it
was divided into. Every caller downstream — the analyst's prompt, the release artifact, the
state a tablet resumes from — asks `final_segments` and repeats none of it.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.db.models.internalization_room import IRSegment, IRSession


def slice_moved(segment: IRSegment, take_id: str, starts_ms: int, ends_ms: int) -> bool:
    """Whether a new version points at different audio from the one it replaces.

    The one expression of "is this the mother tongue re-recorded, or only the explanation
    redone", used by the invariant below and by the route that has to decide it before it
    keeps anything.
    """
    return (
        segment.take_id != take_id or segment.starts_ms != starts_ms or segment.ends_ms != ends_ms
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
) -> IRSegment:
    """Write one stretch: the slice of a recording, and what the team told back about it.

    ``parent`` makes it a stretch divided out of another, which stops the other counting as a
    final unit. ``replaces`` makes it a new version of one position: the earlier row stops
    counting and names this one as what took its place, and stays exactly where it is.

    **A version whose mother-tongue slice moved may not carry a telling-back with it.** The
    product has two corrections and not three: redoing only the explanation, which leaves the
    native audio exactly where it is, and re-recording the native, which always means the
    explanation is redone after it. So a new version over an unchanged slice takes its new
    explanation here, and one that points somewhere else is refused an explanation outright —
    the old one belongs to audio nobody will hear again.

    Refused rather than defaulted. A default is overridden by the next caller who has an
    explanation in hand and no reason to think twice; a refusal is what makes the forbidden
    state unreachable.

    **A stretch that no longer counts cannot be replaced.** A tablet retrying a replacement it
    already sent lands on the row it superseded: the successor would take a position another
    current row already holds, which the index refuses with a 500 nobody in the room can read —
    and once a telling-back has been started over there is no current row left to collide with,
    so the same call would quietly bring a stretch back from the recording the team threw away.

    **A stretch that was divided cannot be replaced as a unit.** Its children would go on
    pointing at the retired row, which the walk in `final_segments` starts too high up to
    reach, and they would drop out of the reading with nothing saying so. It is refused
    rather than repaired because the parent stopped being a unit the moment it was divided:
    what gets re-recorded is a child, one at a time.

    The retired row is stamped before the successor is inserted, not after. The two share a
    position, and the index that keeps one position to one current stretch is checked per
    statement — inserting first would put both of them under it at once.
    """
    refuse_a_slice_that_is_not_one(starts_ms, ends_ms)

    if (
        replaces is not None
        and (bridge_take_id is not None or transcript is not None)
        and slice_moved(replaces, take_id, starts_ms, ends_ms)
    ):
        raise ValidationError(
            "A stretch re-recorded in the mother tongue starts with no telling-back: "
            "the explanation of the recording it replaces does not carry over"
        )

    if replaces is not None:
        if replaces.superseded_at is not None:
            raise ValidationError(
                "This stretch no longer counts: it was already replaced, or the telling-back "
                "it belonged to was started over"
            )
        if any(row.parent_id == replaces.id for row in await _current(db, session.id)):
            raise ValidationError(
                "A stretch that was divided is no longer a unit: replace one of the stretches "
                "it was divided into, not the stretch itself"
            )
        parent_id = replaces.parent_id
        ordinal = replaces.ordinal
    else:
        parent_id = parent.id if parent is not None else None
        ordinal = await _next_ordinal(db, session.id, parent_id)

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
        bridge_take_id=bridge_take_id,
        transcript=transcript,
    )
    db.add(segment)
    await db.commit()
    await db.refresh(segment)
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
    if any(row.parent_id == segment.id for row in await _current(db, session.id)):
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


async def divided_segments(db: AsyncSession, session_id: str) -> list[IRSegment]:
    """The stretches that were divided: current, and no longer a leaf.

    They fall between the two lists the handoff used to carry — not final units, because they
    were divided, and not retired, because nothing replaced them. What the team said about the
    whole stretch, before they heard two ideas in it, vanished from the artifact in silence.

    The same class of loss as a replaced stretch, which the handoff carries on purpose. The
    verb that creates the state is what has to carry it.
    """
    rows = await _current(db, session_id)
    divided = {row.parent_id for row in rows if row.parent_id is not None}
    return [row for row in rows if row.id in divided]


async def final_segments(db: AsyncSession, session_id: str) -> list[IRSegment]:
    """The stretches that count, in the order the team told them.

    Current and leaf, which is the whole selection rule of the room in one place. The order is
    a walk of the hierarchy rather than a column, so a replacement written long after its
    neighbours still reads where its position is — the order the team told in, not the order
    the rows landed in.

    Ordered here rather than in SQL because a session holds tens of rows and the walk is the
    same on both databases. `takes_of` is the reminder: an ordering left to the engine read one
    way on SQLite and upside down on the one that serves a real team.
    """
    rows = await _current(db, session_id)
    children: dict[str | None, list[IRSegment]] = {}
    for row in rows:
        children.setdefault(row.parent_id, []).append(row)

    ordered: list[IRSegment] = []

    def walk(parent_id: str | None) -> None:
        for row in children.get(parent_id, []):
            if children.get(row.id):
                walk(row.id)
            else:
                ordered.append(row)

    walk(None)
    return ordered


def told_back(segments: list[IRSegment]) -> list[IRSegment]:
    """Of those stretches, the ones the team has actually explained in the bridge language.

    A stretch whose mother-tongue recording was just replaced is a real unit and the tablet
    has to see it, but it carries nothing the team said — and nothing is not a text. It
    reached the analyst as a literal ``None``, a line nobody uttered, which the analyst then
    compared against the map and could raise a finding on.

    Kept separate from `final_segments` because the two questions are different: which
    stretches count, and which of them are evidence. Both the numbering the analyst is given
    and the reading of its answer come from this one list, so they cannot drift apart.
    """
    return [segment for segment in segments if segment.transcript is not None]


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


async def retire_every_segment(db: AsyncSession, session_id: str) -> None:
    """Stop every current stretch of a session counting, with nothing taking its place.

    This is a telling-back started over on a recording the team threw away, so there is no
    successor to name — which is why what stops a stretch counting and what replaced it are
    two separate facts.
    """
    at = datetime.now(UTC)
    for segment in await _current(db, session_id):
        segment.superseded_at = at
    await db.commit()


async def _current(db: AsyncSession, session_id: str) -> list[IRSegment]:
    result = await db.execute(
        select(IRSegment)
        .where(IRSegment.session_id == session_id, IRSegment.superseded_at.is_(None))
        .order_by(IRSegment.ordinal, IRSegment.created_at)
    )
    return list(result.scalars().all())


async def _next_ordinal(db: AsyncSession, session_id: str, parent_id: str | None) -> int:
    """One past the last of its own siblings.

    Counted over the current ones only, so a session whose telling-back was started over
    numbers the new stretches from the beginning again. Ordinals order; they do not need to
    be dense.
    """
    siblings = [row for row in await _current(db, session_id) if row.parent_id == parent_id]
    return max((row.ordinal for row in siblings), default=0) + 1
