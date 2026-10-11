from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRCoverageEvent, IRSession
from app.services.internalization_room.canon.kept import reading_the_canon_of
from app.services.internalization_room.coverage import (
    CoverageStatus,
    initial_state,
    is_panorama,
    ranks,
)
from app.services.internalization_room.live import live
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

    This is the reading a *team's* coverage comes from, for the Desk. A session no longer
    opens on it: from ENG-1237 every new session starts at ``initial_state``, as hers does,
    and from ENG-803 until then ``create_session`` seeded ``coverage_state`` from this. It is
    answered here rather than read off a row because the row is one session's and this is the
    team's.

    One window function over one pass picks the row that answers both halves: the events of a
    bead are ordered by how far each took it, ties broken by which came first, and the winner
    carries its own status *and* its own session. Thirty-four beads would otherwise be
    thirty-four round trips for the same rows.

    Ordering by rank rather than by recency is the whole point, and it answers the rows that
    are written. Every new session opens at ``initial_state``, so a bead the team engaged on
    Tuesday earns a fresh ``surfaced`` event the moment a new session's Guide mentions it again:
    against that session's own tracker it really did move, and at team level it moved nowhere.
    Taking the most recent event would answer ``engaged`` beside the newer session, and tell a
    facilitator that a conversation which only surfaced the bead is where it was worked.

    The tie is broken towards the *earliest* of the events that reached the standing status.
    Once a bead is engaged it has nowhere further to go, so a later session reaching ``engaged``
    again moved nothing; the session named is the one the bead last actually moved in.

    Scoped by project **and** passage. An element key belongs to the canon, not to a team —
    two teams working Ruth both carry ``being:B3``, and Naomi appears in several passages —
    so neither half alone names a bead. A session that never said whose it was carries a null
    ``project_id`` and is nobody's work rather than everybody's; it is filtered out by the
    same equality, which is the intended answer here and not a row lost in silence.

    What it cannot do is see work the classifier discarded, and for two releases that was
    most of it: ``classify_coverage`` read keys the prompt does not produce (ENG-569), and
    then routed the array it does produce through a table holding two of its three statuses
    (ENG-615), so a bead the team worked on the Guide's terms was logged and thrown away.
    Both are fixed. This answers the events that were written, which is all it ever claimed.

    Live events only, and on live sessions only (ADR 0047): a settle still running when a
    Zerar landed writes an unstamped bead on an archived session, and the session's own stamp
    is what keeps that bead out of the next session's necklace.
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
        .join(IRSession, IRSession.id == IRCoverageEvent.session_id)
        .where(
            IRCoverageEvent.project_id == project_id,
            IRCoverageEvent.pericope == pericope,
            live(IRCoverageEvent),
            live(),
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


async def necklace_of(db: AsyncSession, session: IRSession) -> dict[str, str]:
    """Where every bead of a session's spine stood when that session ended.

    A session's own spine. A session opened from ENG-803 until ENG-1237 had its
    ``coverage_state`` seeded from the team's whole history, so for such a session the two
    differ by exactly the beads it was handed; a session opened since starts at the spine and
    the two agree. Read the column for what the room is working against; read this for what
    this conversation itself did.

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
    That one answers a *session's* spine — its own steps laid over the canon's, which is what
    that conversation itself did. This answers the *team's* passage. RF-06 asks a
    card for the portrait at that moment and the acceptance criterion is that it match what the
    necklace showed then — and the necklace is the team's, folded across every conversation
    that strung it. A card drawn
    from one session's steps would sit under a panel showing everything the team has done and
    disagree with it, which is the one thing the issue says must not happen. The two are near
    enough to be mistaken for one another, which is why this paragraph is here.

    The fold is ``necklace_with_touches``'s, deliberately: furthest rank per bead, never most
    recent. Every new session opens at ``initial_state``, so a bead engaged on Tuesday earns a
    fresh ``surfaced`` step the moment a new session's Guide mentions it: against that
    session's own tracker it moved, and at team level it moved nowhere. Taking the latest step
    would walk a bead backwards on the newer card.

    Scoped by project **and** passage, for the reason an element key is the canon's: two teams
    working Ruth both carry ``being:B3``. Both scopes come free here — each session carries its
    own team and its own pericope, so one call folds one team's history or a page spanning many
    teams alike — which is also why this needs no query beyond the one it already makes.

    A panorama has no spine and no coverage: it prepares the team to enter the book and asks
    no retelling of them. It is answered with nothing rather than refused, because a panorama
    is a conversation the team really held and dropping it would hide it from their history.
    """
    spines: dict[str, dict[str, str]] = {}
    for session in sessions:
        with reading_the_canon_of(session.canon_pin):
            spines[session.id] = (
                {} if is_panorama(session.pericope) else initial_state(session.pericope)
            )
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

    for (_team, pericope), conversations in _by_passage(sessions).items():
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


def _by_passage(sessions: Sequence[IRSession]) -> dict[tuple[str | None, str], list[IRSession]]:
    """Conversations grouped by the team and the passage they were about.

    The accumulation is a running maximum per team's passage, so each group is ordered on its
    own by `_last_word`; the caller hands these over newest first, which is the order the Desk
    reads them in and not the order they can be folded in.
    """
    passages: dict[tuple[str | None, str], list[IRSession]] = {}
    for session in sessions:
        passages.setdefault((session.project_id, session.pericope), []).append(session)
    return passages


async def last_bead_moved_in_session(db: AsyncSession, *, session_id: str) -> str | None:
    """Which bead this session's own history moved most recently, or nothing if it moved none.

    Scoped to one session rather than to the team's whole passage: a bead the same
    passage's canon carries that another session moved — another team's, or an earlier
    session of this same team — was not what *this* room was on, and lending it would
    name a bead nobody in this conversation ever raised a hand about.

    Reads the same table `record_transitions` writes, and nothing else, so a raised
    question can never anchor to a bead the tracker did not actually record moving.
    """
    result = await db.execute(
        select(IRCoverageEvent.element_key)
        .where(IRCoverageEvent.session_id == session_id)
        .order_by(IRCoverageEvent.at.desc(), IRCoverageEvent.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


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
