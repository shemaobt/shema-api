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

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.project import Project
from app.models.internalization_room import PericopePosition
from app.models.team import ActivePassageView, FacilitatorTeamDetail
from app.services.internalization_room.canon.elements import scene_key, scene_of
from app.services.internalization_room.canon.parse_map import ROOM_BOOK, load_map
from app.services.internalization_room.coverage_events import (
    furthest_by_passage,
    necklace_with_touches,
)
from app.services.internalization_room.progression import resolve, standing
from app.services.project.list_facilitator_teams import _facilitated_projects, team_cards
from app.services.project.team_state import team_state


async def read_facilitator_team(
    db: AsyncSession, user: User, team_id: str, *, now: datetime | None = None
) -> FacilitatorTeamDetail | None:
    """This team as its own screen reads it, or ``None`` when the caller cannot reach it.

    ``None`` and not an exception, and not two different answers: a team that does not exist
    and one that is not the caller's are indistinguishable from here, which is what lets the
    route answer them with one refusal. Telling them apart is the enumeration ENG-443 closed.

    Three statements and none of them grows: the team's row, the whole of its coverage history
    for the book, and the necklace of the passage it is standing on. The second serves both the
    active passage and ``closed_total`` from one read rather than asking twice.

    Measured on a throwaway Postgres 17 with 210,000 events over 200 teams, ``ANALYZE``d, and
    not against an empty table — both reads take a **Bitmap Index Scan** on
    ``ix_ir_coverage_events_element_touched``:

    ==========================  =======  =========  ======
    read                        buffers  time       rows
    ==========================  =======  =========  ======
    the book, for one team           31  1.86 ms       350
    the necklace of one passage       5  0.065 ms       25
    ==========================  =======  =========  ======

    Neither is a sequential scan, and the number that matters is that the cost is the size of
    the **answer** rather than the size of the installation.
    """
    moment = now or datetime.now(UTC)
    scope = _facilitated_projects(user)
    row = (await db.execute(team_cards(scope).where(Project.id == team_id))).first()
    if row is None:
        return None

    reached = (await furthest_by_passage(db, project_ids=[team_id])).get(team_id, {})
    here = resolve(reached)
    closed = sum(1 for entry in standing(reached) if entry.position is PericopePosition.CLOSED)

    return FacilitatorTeamDetail(
        team_id=row.id,
        name=row.name,
        mother_tongue=row.mother_tongue,
        active_passage=(
            None
            if here is None
            else ActivePassageView(pericope=here, reference=load_map(here).reference)
        ),
        state=team_state(
            book_closed=here is None,
            last_activity_at=row.last_activity_at,
            now=moment,
        ),
        open_raised_hands=row.open_hands,
        device_count=row.device_count,
        last_activity_at=row.last_activity_at,
        closed_total=closed,
        scene_the_team_is_in=await _scene_they_are_in(db, team_id=team_id, pericope=here),
    )


async def _scene_they_are_in(
    db: AsyncSession, *, team_id: str, pericope: str | None, book: str = ROOM_BOOK
) -> str | None:
    """The scene of the bead this team moved most recently, named as that scene's own bead.

    ``BeadHistory.at`` is when a bead last *actually* moved — the reconstruction breaks ties
    towards the earliest event that reached the standing status — so the greatest of them is
    the team's most recent real movement and not merely the last turn that mentioned something.

    Null rather than a guess in two cases, and both are the same refusal. A preservation rule
    belongs to the passage and to none of its scenes. And a bead the canon deduped across
    scenes — Naomi appears in four of P01's and her bead says the first — cannot say where a
    team is standing either; naming its first appearance would be a confident wrong answer,
    which on a position is worse than none. `scene_of` is where that decision lives.
    """
    if pericope is None:
        return None

    history = await necklace_with_touches(db, project_id=team_id, pericope=pericope)
    if not history:
        return None

    # Only the beads that belong to exactly one scene can answer this. The rest are entities
    # deduped across the passage, carrying the scene they first appeared in — see `scene_of`.
    answers = scene_of(pericope, book)
    moved = [key for key in history if key in answers]
    if not moved:
        return None

    latest = max(moved, key=lambda key: history[key].at)
    return scene_key(answers[latest])
