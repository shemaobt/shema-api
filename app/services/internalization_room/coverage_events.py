from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRCoverageEvent, IRSession
from app.services.internalization_room.coverage import CoverageStatus, ranks

_RANK_OF = ranks()


def record_transitions(
    db: AsyncSession,
    session: IRSession,
    *,
    before: dict[str, str],
    after: dict[str, str],
) -> list[IRCoverageEvent]:
    """Write one event for each bead the merge actually moved.

    The comparison is the whole point: the classifier reports the tracker it was given
    plus whatever it heard, so most merges change nothing, and a row written before the
    two states are compared would make this a turn log under a coverage name. Movement is
    one-way, so a status that would step back is not a transition and leaves no event.

    Added to the caller's transaction and not committed here — the history and the state
    it explains reach the database together or not at all.
    """
    events = [
        IRCoverageEvent(
            session_id=session.id,
            project_id=session.project_id,
            pericope=session.pericope,
            element_key=element_key,
            status=status,
        )
        for element_key, status in after.items()
        if _RANK_OF[status]
        > _RANK_OF[before.get(element_key, CoverageStatus.NOT_ENCOUNTERED.value)]
    ]
    db.add_all(events)
    return events


@dataclass(frozen=True)
class BeadHistory:
    """How far a team ever took one bead, and which of its sessions did it last."""

    status: CoverageStatus
    session_id: str
    at: datetime


async def necklace_with_touches(
    db: AsyncSession, *, project_id: str, pericope: str
) -> dict[str, BeadHistory]:
    """Where a team's whole necklace stands, and who moved each bead last. One statement.

    This is the only honest reading of a *team's* coverage. ``ir_sessions.coverage_state`` is
    one session's tracker and nothing more: ``create_session`` opens every session at
    ``initial_state``, so a bead engaged on Tuesday reads ``not_encountered`` on Wednesday's
    session. Laying the team's events over the spine is what makes the necklace outlive the
    conversations that strung it.

    One window function over one pass picks the row that answers both halves: the events of a
    bead are ordered by how far each took it, ties broken by which came first, and the winner
    carries its own status *and* its own session. Thirty-four beads would otherwise be
    thirty-four round trips for the same rows.

    Ordering by rank rather than by recency is the whole point, and it is not an edge case.
    Every session opens at ``initial_state``, so a bead the team engaged on Tuesday earns a
    fresh ``surfaced`` event the moment Wednesday's Guide mentions it again — against
    Wednesday's own tracker it really did move. At team level it moved nowhere. Taking the
    most recent event instead would answer ``engaged`` beside Wednesday's session, and tell a
    facilitator that a conversation which only surfaced the bead is where it was worked.

    The tie is broken towards the *earliest* of the events that reached the standing status.
    Once a bead is engaged it has nowhere further to go, so a later session reaching ``engaged``
    again moved nothing; the session named is the one the bead last actually moved in.

    Scoped by project **and** passage. An element key belongs to the canon, not to a team —
    two teams working Ruth both carry ``being:B3``, and Naomi appears in several passages —
    so neither half alone names a bead. A session that never said whose it was carries a null
    ``project_id`` and is nobody's work rather than everybody's; it is filtered out by the
    same equality, which is the intended answer here and not a row lost in silence.

    What it cannot do is see work the classifier discarded. ``classify_coverage`` reads keys
    the prompt does not produce, so well-formed replies are dropped, no merge happens and no
    event is written — measured in ENG-441 and left to the room line to fix. Until it is, this
    answers a necklace that never moved, and answers it accurately.
    """
    standing = func.row_number().over(
        partition_by=IRCoverageEvent.element_key,
        order_by=(
            case(_RANK_OF, value=IRCoverageEvent.status, else_=0).desc(),
            IRCoverageEvent.at.asc(),
            IRCoverageEvent.id.asc(),
        ),
    )
    walked = (
        select(
            IRCoverageEvent.element_key,
            IRCoverageEvent.session_id,
            IRCoverageEvent.at,
            IRCoverageEvent.status,
            standing.label("standing"),
        )
        .where(
            IRCoverageEvent.project_id == project_id,
            IRCoverageEvent.pericope == pericope,
        )
        .subquery()
    )
    result = await db.execute(
        select(walked.c.element_key, walked.c.session_id, walked.c.at, walked.c.status).where(
            walked.c.standing == 1
        )
    )
    return {
        element_key: BeadHistory(status=CoverageStatus(status), session_id=session_id, at=at)
        for element_key, session_id, at, status in result.all()
    }


async def furthest_by_passage(
    db: AsyncSession, *, project_ids: Sequence[str]
) -> dict[str, dict[str, dict[str, str]]]:
    """How far a roll of teams took every bead of every passage they have touched.

    `{project_id: {pericope: {element_key: status}}}`, and a team, passage or bead with no
    events is absent rather than present and empty — the caller reads an absence as "not
    encountered", which is what it is.

    One statement for the whole roll. `necklace_with_touches` answers one team and one
    passage, which is the Desk's element list; progression asks the opposite shape — every
    passage of every team on a screen — and asking it that way would be fourteen round trips
    for a facilitator with fourteen teams, on the screen that opens first.

    **The ids are passed in hand and never as a subquery.** Measured on a seeded Postgres 16 —
    210,000 events over 200 teams, `ANALYZE`d, answering the fourteen a facilitator holds:

    ==================  ==========================================  =======  =======
    scope spelled as    plan                                        buffers  time
    ==================  ==========================================  =======  =======
    ids in hand         Bitmap Index Scan on the element index          461  19.9 ms
    ``IN (subquery)``   Seq Scan over all 210,000, then a Hash Join    4567  48.7 ms
    ==================  ==========================================  =======  =======

    Same 4,900 rows out of both. The subquery form never touches
    `ix_ir_coverage_events_element_touched` at all, and its cost is the size of the
    *installation* rather than the size of the answer — so it works until the installation
    grows. An empty roll is answered without asking the database anything, because `IN ()` is
    a statement whose answer is known.

    **The furthest status per bead, not a count of them.** The caller compares against the
    canon's own spine, so a passage whose elements were renamed leaves events pointing at keys
    nobody serves any more, and those must not be able to close it. `MAX` over the status
    string would order `engaged` before `surfaced` alphabetically, so the scale is taught to
    SQL by `ranks()` — the same one `coverage` keeps — and the winning row's own status is
    carried back rather than the rank it won with.
    """
    if not project_ids:
        return {}

    standing = func.row_number().over(
        partition_by=(
            IRCoverageEvent.project_id,
            IRCoverageEvent.pericope,
            IRCoverageEvent.element_key,
        ),
        order_by=(
            case(_RANK_OF, value=IRCoverageEvent.status, else_=0).desc(),
            IRCoverageEvent.at.asc(),
            IRCoverageEvent.id.asc(),
        ),
    )
    walked = (
        select(
            IRCoverageEvent.project_id,
            IRCoverageEvent.pericope,
            IRCoverageEvent.element_key,
            IRCoverageEvent.status,
            standing.label("standing"),
        )
        .where(IRCoverageEvent.project_id.in_(project_ids))
        .subquery()
    )
    result = await db.execute(
        select(
            walked.c.project_id,
            walked.c.pericope,
            walked.c.element_key,
            walked.c.status,
        ).where(walked.c.standing == 1)
    )

    reached: dict[str, dict[str, dict[str, str]]] = {}
    for project_id, pericope, element_key, status in result.all():
        reached.setdefault(project_id, {}).setdefault(pericope, {})[element_key] = status
    return reached
