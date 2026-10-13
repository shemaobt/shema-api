"""One team at its own address, and the two facts only that address can answer.

The queue's row and this answer are built from the same subqueries on purpose: a screen that
draws a team from here and a card that draws the same team from there are not allowed to
disagree, and the way to guarantee that is one query shape, narrowed.

**Cost is not why this route exists** — the queue costs two statements for fourteen teams and
two for one, so a client filtering it would pay the same. What it cannot do is refuse: the
three sibling panels answer 404 with an identical body for "not yours" and for "no such team",
and an empty list answers neither. See ENG-536.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Label, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import CanonNotKept
from app.db.models.auth import User
from app.db.models.internalization_room import IRSession
from app.db.models.project import Project
from app.models.internalization_room import PericopePosition
from app.models.team import ActivePassageView, FacilitatorTeamDetail
from app.services.internalization_room.canon.elements import scene_key, scene_of
from app.services.internalization_room.canon.kept import reading_the_canon_of
from app.services.internalization_room.canon.parse_map import ROOM_BOOK, load_map
from app.services.internalization_room.coverage_events import necklace_with_touches
from app.services.internalization_room.entered import latest_entered_first
from app.services.internalization_room.latest_by_passage import latest_releases
from app.services.internalization_room.live import live
from app.services.internalization_room.progression import finished_passages, resolve, standing
from app.services.project.facilitated_scope import readable_projects, writable_project_ids
from app.services.project.list_facilitator_teams import team_cards
from app.services.project.team_state import team_state


async def read_facilitator_team(
    db: AsyncSession, user: User, team_id: str, *, now: datetime | None = None
) -> FacilitatorTeamDetail | None:
    """This team as its own screen reads it, or ``None`` when the caller cannot reach it.

    ``None`` and not an exception, and not two different answers: a team that does not exist
    and one that is not the caller's are indistinguishable from here, which is what lets the
    route answer them with one refusal. Telling them apart is the enumeration ENG-443 closed.

    Four statements and none of them grows: the team's row, the passages it has finished, its
    latest releases, and the necklace of the passage it is standing on. The second serves both
    the active passage and ``closed_total`` from one read rather than asking twice.

    The necklace read was measured on a throwaway Postgres 17 with 210,000 events over 200
    teams, ``ANALYZE``d and not against an empty table: a **Bitmap Index Scan** on
    ``ix_ir_coverage_events_element_touched``, 5 buffers and 0.065 ms for 25 rows. What that
    number says is that the cost is the size of the **answer** rather than the size of the
    installation, which is the property this route is built on.
    """
    moment = now or datetime.now(UTC)
    scope = await readable_projects(db, user)
    finished = (await finished_passages(db, project_ids=[team_id])).get(team_id, set())
    here = resolve(finished)
    row = (
        await db.execute(
            team_cards(scope).where(Project.id == team_id).add_columns(_the_canon_pin_on(here))
        )
    ).first()
    if row is None:
        return None

    passages = standing(finished, releases=await latest_releases(db, team_id), findings={})
    closed = sum(1 for entry in passages if entry.position is PericopePosition.CLOSED)
    active = None
    if here is not None:
        try:
            with reading_the_canon_of(row.canon_pin):
                active = ActivePassageView(pericope=here, reference=load_map(here).reference)
        except CanonNotKept:
            active = ActivePassageView(pericope=here, reference=None)

    return FacilitatorTeamDetail(
        team_id=row.id,
        name=row.name,
        mother_tongue=row.mother_tongue,
        active_passage=active,
        state=team_state(
            book_closed=here is None,
            last_activity_at=row.last_activity_at,
            now=moment,
        ),
        open_raised_hands=row.open_hands,
        device_count=row.device_count,
        last_activity_at=row.last_activity_at,
        facilitates=team_id in await writable_project_ids(db, user),
        closed_total=closed,
        approved_total=sum(1 for entry in passages if entry.approved),
        scene_the_team_is_in=await _scene_they_are_in(
            db, team_id=team_id, pericope=here, pin=row.canon_pin
        ),
    )


def _the_canon_pin_on(pericope: str | None) -> Label[str | None]:
    return (
        select(IRSession.canon_pin)
        .where(IRSession.project_id == Project.id, IRSession.pericope == pericope, live())
        .order_by(*latest_entered_first())
        .limit(1)
        .scalar_subquery()
        .label("canon_pin")
    )


async def _scene_they_are_in(
    db: AsyncSession,
    *,
    team_id: str,
    pericope: str | None,
    pin: str | None,
    book: str = ROOM_BOOK,
) -> str | None:
    """The scene of the bead this team moved most recently, named as that scene's own bead.

    ``BeadHistory.at`` is when a bead last *actually* moved — the reconstruction breaks ties
    towards the earliest event that reached the standing status — so the greatest of them is
    the team's most recent real movement and not merely the last turn that mentioned something.

    Null rather than a guess for a bead that belongs to no scene: a preservation rule and a
    Level-1 axis belong to the passage and to none of its scenes. `scene_of` is where that
    decision lives.
    """
    if pericope is None:
        return None

    history = await necklace_with_touches(db, project_id=team_id, pericope=pericope)
    if not history:
        return None

    try:
        with reading_the_canon_of(pin):
            answers = scene_of(pericope, book)
    except CanonNotKept:
        return None
    moved = [key for key in history if key in answers]
    if not moved:
        return None

    latest = max(moved, key=lambda key: history[key].at)
    return scene_key(answers[latest])
