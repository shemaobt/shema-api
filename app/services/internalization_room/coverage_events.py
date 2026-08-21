from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRCoverageEvent, IRSession
from app.services.internalization_room.coverage import (
    CoverageStatus,
    initial_state,
    is_panorama,
    ranks,
)
from app.services.internalization_room.session_end import as_utc

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

    One statement. The furthest status per element is taken by the database — the scale lives
    in ``coverage.ranks()`` and is handed to SQL as the case that orders it, because a status
    name sorts alphabetically and ``engaged`` would lose to ``surfaced``.
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


async def necklaces_of(
    db: AsyncSession, sessions: Sequence[IRSession]
) -> dict[str, dict[str, str]]:
    """The necklace as it stood at the end of each of these sessions.

    **A different question from ``necklace_of`` above, not a better answer to the same one.**
    That one answers a *session's* spine and answers it correctly: ``create_session`` opens
    every session at ``initial_state``, so a session's own steps really are its own state at
    the end. This answers the *team's* passage. RF-06 asks a card for the portrait at that
    moment and the acceptance criterion is that it match what the necklace showed then — and
    the necklace is the team's, folded across every conversation that strung it. A card drawn
    from one session's steps would sit under a panel showing everything the team has done and
    disagree with it, which is the one thing the issue says must not happen. The two are near
    enough to be mistaken for one another, which is why this paragraph is here.

    The fold is ``necklace_with_touches``'s, deliberately: furthest rank per bead, never most
    recent. Every session opens at ``initial_state``, so a bead engaged on Tuesday earns a
    fresh ``surfaced`` step the moment Wednesday's Guide mentions it — against Wednesday's own
    tracker it moved, and at team level it moved nowhere. Taking the latest step instead would
    walk a bead backwards on the newer card.

    Scoped by project **and** passage, for the reason an element key is the canon's: two teams
    working Ruth both carry ``being:B3``. Both scopes come free here — the caller hands over
    one team's sessions and each carries its own pericope — which is also why this needs no
    query beyond the one it already makes.

    A panorama has no spine and no coverage: it prepares the team to enter the book and asks
    no retelling of them. It is answered with nothing rather than refused, because a panorama
    is a conversation the team really held and dropping it would hide it from their history.
    """
    spines = {
        session.id: ({} if is_panorama(session.pericope) else initial_state(session.pericope))
        for session in sessions
    }
    if not spines:
        return {}

    result = await db.execute(
        select(
            IRCoverageEvent.session_id,
            IRCoverageEvent.element_key,
            _FURTHEST_RANK,
            func.max(IRCoverageEvent.at),
        )
        .where(IRCoverageEvent.session_id.in_(spines))
        .group_by(IRCoverageEvent.session_id, IRCoverageEvent.element_key)
    )
    moved: dict[str, dict[str, int]] = {}
    ended: dict[str, datetime] = {}
    for session_id, element_key, rank, at in result.all():
        moved.setdefault(session_id, {})[element_key] = rank
        stamped = as_utc(at)
        ended[session_id] = max(ended.get(session_id, stamped), stamped)

    for pericope, conversations in _by_passage(sessions).items():
        if is_panorama(pericope):
            continue
        standing: dict[str, int] = {}
        for session in sorted(conversations, key=lambda s: _last_word(s, ended)):
            for element_key, rank in moved.get(session.id, {}).items():
                standing[element_key] = max(standing.get(element_key, 0), rank)
            spine = spines[session.id]
            for element_key, rank in standing.items():
                if element_key in spine:
                    spine[element_key] = _STATUS_AT[rank]
    return spines


def _last_word(session: IRSession, ended: dict[str, datetime]) -> tuple[datetime, str]:
    """When this conversation last moved a bead, which is what puts it in the running order.

    ``created_at`` alone will not do it. It is the database's clock through
    ``server_default=func.now()``, which on SQLite has a resolution of one second — two
    conversations opened in the same second tie, and the accumulation then runs in whatever
    order their ids fell in, walking a bead backwards on the earlier card. Measured: two of
    these tests went red on exactly that. The events' own ``at`` is stamped in the application
    to the microsecond, for the neighbouring reason recorded on ``IRCoverageEvent``.

    A conversation that moved nothing has no such instant and falls back to when it opened,
    which is right: it has nothing of its own to place and simply inherits what stood before.
    """
    return (ended.get(session.id, as_utc(session.created_at)), session.id)


def _by_passage(sessions: Sequence[IRSession]) -> dict[str, list[IRSession]]:
    """One team's conversations, grouped by the passage they were about.

    The accumulation is a running maximum per passage, so each group is ordered on its own by
    `_last_word`; the caller hands these over newest first, which is the order the Desk reads
    them in and not the order they can be folded in.
    """
    passages: dict[str, list[IRSession]] = {}
    for session in sessions:
        passages.setdefault(session.pericope, []).append(session)
    return passages


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
