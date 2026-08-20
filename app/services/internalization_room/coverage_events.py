from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRCoverageEvent, IRSession
from app.services.internalization_room.coverage import CoverageStatus, initial_state, ranks

_RANK_OF = ranks()
_STATUS_AT = {rank: status for status, rank in _RANK_OF.items()}
_FURTHEST_RANK = func.max(case(_RANK_OF, value=IRCoverageEvent.status, else_=0))


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


async def necklace_of(db: AsyncSession, session: IRSession) -> dict[str, str]:
    """Where every bead of a session's spine stood when that session ended.

    For a session still running, read ``coverage_state`` instead: it is the same answer
    without the query, and keeping it the fast read is what keeps this table history
    rather than the source of truth.

    One statement. The furthest status per element is taken by the database — the scale
    lives in ``coverage.ranks()`` and is handed to SQL as the case that orders it, because
    a status name sorts alphabetically and ``engaged`` would lose to ``surfaced``. What
    comes back is one row per bead that moved, laid over the untouched spine.

    A panorama session has no spine and no coverage; asking it for a necklace raises, from
    the canon, the same way every other route into a map that does not exist does.
    """
    result = await db.execute(
        select(IRCoverageEvent.element_key, _FURTHEST_RANK)
        .where(IRCoverageEvent.session_id == session.id)
        .group_by(IRCoverageEvent.element_key)
    )
    state = initial_state(session.pericope)
    for element_key, rank in result.all():
        if element_key in state:
            state[element_key] = _STATUS_AT[rank]
    return state


async def last_session_to_touch(
    db: AsyncSession,
    *,
    project_id: str | None,
    pericope: str,
    element_key: str,
) -> str | None:
    """Which session last moved one bead, or nothing if none ever did.

    Scoped by project and passage because an element key is the canon's, not a project's:
    two teams working Ruth carry the same ``being:B3``, and answering without saying whose
    bead it is hands one team the other team's session.
    """
    result = await db.execute(
        select(IRCoverageEvent.session_id)
        .where(
            IRCoverageEvent.project_id == project_id,
            IRCoverageEvent.pericope == pericope,
            IRCoverageEvent.element_key == element_key,
        )
        .order_by(IRCoverageEvent.at.desc(), IRCoverageEvent.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


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
