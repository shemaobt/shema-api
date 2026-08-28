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

    **A stretch that was divided cannot be replaced as a unit.** Its children would go on
    pointing at the retired row, which the walk in `final_segments` starts too high up to
    reach, and they would drop out of the reading with nothing saying so. It is refused
    rather than repaired because the parent stopped being a unit the moment it was divided:
    what gets re-recorded is a child, one at a time.

    The retired row is stamped before the successor is inserted, not after. The two share a
    position, and the index that keeps one position to one current stretch is checked per
    statement — inserting first would put both of them under it at once.
    """
    if replaces is not None and (bridge_take_id is not None or transcript is not None):
        moved = (
            replaces.take_id != take_id
            or replaces.starts_ms != starts_ms
            or replaces.ends_ms != ends_ms
        )
        if moved:
            raise ValidationError(
                "A stretch re-recorded in the mother tongue starts with no telling-back: "
                "the explanation of the recording it replaces does not carry over"
            )

    if replaces is not None:
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
