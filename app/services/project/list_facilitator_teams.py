"""The facilitator's work queue, in one query.

Everything a card draws is answered here: the team, its mother tongue, the passage it is on,
what state that passage is in, how many hands are waiting, how many devices are linked, and
when the team last did anything. The client computes none of it.

**One statement, whatever the size of the roll.** Counting hands or devices per team would be
a round trip per row, and a facilitator with fourteen teams would pay for fourteen — on the
screen that opens first, every time it opens. The counts arrive as grouped subqueries joined
once.

**Every subquery carries the caller's scope, and that is not a tidiness.** Written without it
the counts group the *whole installation* and the join throws away all but fourteen rows: the
plan is a sequential scan of `ir_sessions`, `ir_questions` and `ir_takes` per request, with the
`project_id` indexes never touched. Measured on a seeded Postgres before the scope was pushed
down — three seq scans over 70,000 rows to answer fourteen teams. A query whose cost is the size
of the installation rather than the size of the answer is one that works until the installation
grows.

The three numbers on the envelope are not the same kind of fact. ``teams`` answers the
query; ``serves_any_team`` and ``open_hands_total`` answer the facilitator, and neither
narrows with the restriction.
"""

from datetime import UTC, datetime

from sqlalchemy import ColumnElement, Select, func, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.sql.selectable import Subquery

from app.core.enums import ProjectRole
from app.db.models.auth import User
from app.db.models.device import Device
from app.db.models.internalization_room import (
    IRQuestion,
    IRQuestionStatus,
    IRSession,
    IRTake,
)
from app.db.models.language import Language
from app.db.models.project import Project, ProjectUserAccess
from app.models.team import (
    ActivePassageView,
    FacilitatorTeamView,
    TeamFilter,
    TeamListingResponse,
)
from app.services.internalization_room.canon.parse_map import load_map
from app.services.internalization_room.progression import active_passages
from app.services.project.team_restriction import as_work_queue, matching
from app.services.project.team_state import team_state


def _facilitated_projects(user: User) -> Select | None:
    """The project ids the caller reaches, or ``None`` when that is every one of them.

    ``None`` rather than a select of every id on purpose: a platform admin's scope is "no
    restriction", and spelling it as a subquery listing the installation would put that list
    inside five other subqueries for nothing.
    """
    if user.is_platform_admin:
        return None

    return select(ProjectUserAccess.project_id).where(
        ProjectUserAccess.user_id == user.id,
        ProjectUserAccess.role == ProjectRole.FACILITATOR,
    )


def _within(column: InstrumentedAttribute[str | None], scope: Select | None) -> ColumnElement[bool]:
    """Confine one subquery to the caller's teams.

    Falls back to "has a project at all" for a platform admin, which is what an unrestricted
    scope means here. A null project belongs to no team either way, and ``IN`` already excludes
    it — the explicit test is what keeps the admin's case honest rather than accidental.
    """
    if scope is None:
        return column.is_not(None)

    return column.in_(scope)


def _last_activity_subquery(scope: Select | None) -> Subquery:
    """The last moment the team did anything, across everything it can do.

    All three tables, not just the session's own row: a raised hand does not update the
    session it was asked in, and a count that misses it errs **low**. On a work queue that is
    the worse direction — a facilitator does not go looking for what does not appear.
    """
    moments = union_all(
        select(IRSession.project_id.label("project_id"), IRSession.updated_at.label("at")).where(
            _within(IRSession.project_id, scope)
        ),
        select(IRQuestion.project_id.label("project_id"), IRQuestion.created_at.label("at")).where(
            _within(IRQuestion.project_id, scope)
        ),
        select(IRTake.project_id.label("project_id"), IRTake.created_at.label("at")).where(
            _within(IRTake.project_id, scope)
        ),
    ).subquery()
    return (
        select(moments.c.project_id, func.max(moments.c.at).label("last_activity_at"))
        .group_by(moments.c.project_id)
        .subquery()
    )


def _open_hands_subquery(scope: Select | None) -> Subquery:
    return (
        select(IRQuestion.project_id.label("project_id"), func.count().label("open_hands"))
        .where(
            IRQuestion.status == IRQuestionStatus.OPEN,
            _within(IRQuestion.project_id, scope),
        )
        .group_by(IRQuestion.project_id)
        .subquery()
    )


def _device_count_subquery(scope: Select | None) -> Subquery:
    """Linked devices, counted the same way ``list_team_devices`` lists them.

    An unlinked device keeps its ``project_id`` so the row still records where the tablet
    was, which is why the filter has to be repeated rather than assumed: the number beside a
    team and the length of that team's device list are not allowed to disagree.
    """
    return (
        select(Device.project_id.label("project_id"), func.count().label("device_count"))
        .where(Device.unlinked_at.is_(None), _within(Device.project_id, scope))
        .group_by(Device.project_id)
        .subquery()
    )


async def list_facilitator_teams(
    db: AsyncSession,
    user: User,
    *,
    search: str = "",
    chosen: TeamFilter = TeamFilter.ALL,
    now: datetime | None = None,
) -> TeamListingResponse:
    """The caller's teams, restricted and ordered, beside two facts the restriction misses.

    A platform admin reaches every team, as they do on every other facilitator route: they
    already hold every other power here, and scoping the one person able to investigate an
    installation to nothing would leave nobody able to look at it.

    A row whose ``project_id`` is null belongs to no team and is counted for none. That is the
    only honest answer — there is nothing to attribute it to — and it is worth knowing that it
    is the common case today rather than the exception: the room's app does not send its
    device credential yet, so sessions and questions are written with no project at all.
    """
    moment = now or datetime.now(UTC)
    scope = _facilitated_projects(user)
    activity = _last_activity_subquery(scope)
    hands = _open_hands_subquery(scope)
    devices = _device_count_subquery(scope)

    query = (
        select(
            Project.id,
            Project.name,
            Language.name.label("mother_tongue"),
            func.coalesce(hands.c.open_hands, 0).label("open_hands"),
            func.coalesce(devices.c.device_count, 0).label("device_count"),
            activity.c.last_activity_at,
        )
        .join(Language, Language.id == Project.language_id)
        .outerjoin(activity, activity.c.project_id == Project.id)
        .outerjoin(hands, hands.c.project_id == Project.id)
        .outerjoin(devices, devices.c.project_id == Project.id)
    )

    if scope is not None:
        query = query.where(Project.id.in_(scope))

    rows = (await db.execute(query)).all()
    # The ids in hand rather than the scope again: `IN (subquery)` costs the planner the
    # index on `ir_coverage_events`, and these rows already name every team the answer is
    # about. One statement for the whole roll, not one per card.
    here = await active_passages(db, project_ids=[row.id for row in rows])

    every_team = [
        FacilitatorTeamView(
            team_id=row.id,
            name=row.name,
            mother_tongue=row.mother_tongue,
            active_passage=_passage(here[row.id]),
            state=team_state(
                passage_done=here[row.id] is None,
                last_activity_at=row.last_activity_at,
                now=moment,
            ),
            open_raised_hands=row.open_hands,
            device_count=row.device_count,
            last_activity_at=row.last_activity_at,
        )
        for row in rows
    ]

    return TeamListingResponse(
        teams=as_work_queue(matching(every_team, search=search, chosen=chosen)),
        serves_any_team=bool(every_team),
        open_hands_total=sum(team.open_raised_hands for team in every_team),
    )


def _passage(pericope: str | None) -> ActivePassageView | None:
    """The passage by both its names, or nothing at all at the end of the book.

    `None` is the answer for a team that has closed every passage, and it is a position rather
    than a missing value: there is no passage they are on. A card drawn for such a team shows
    its last one closed, which is ENG-469's criterion and is only sayable if `active_passage`
    can be absent.

    A team with no session yet is not that case — it is on the first passage, because that is
    where the resolution puts it, and the card is drawn on the passage its first session will
    be about rather than on nothing.

    The reference comes off the canon verbatim and a pericope the canon does not hold raises
    rather than answering blank. A passage the API cannot name is a data fault, and a card
    quietly missing its reference is the kind of fault nobody reports.
    """
    if pericope is None:
        return None
    return ActivePassageView(pericope=pericope, reference=load_map(pericope).reference)
