from __future__ import annotations

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
