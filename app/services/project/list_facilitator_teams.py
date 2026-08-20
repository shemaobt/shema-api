"""The facilitator's work queue, in one query.

Everything a card draws is answered here: the team, its mother tongue, the passage it is on,
what state that passage is in, how many hands are waiting, how many devices are linked, and
when the team last did anything. The client computes none of it.

**One statement, whatever the size of the roll.** Counting hands or devices per team would be
a round trip per row, and a facilitator with fourteen teams would pay for fourteen — on the
screen that opens first, every time it opens. The counts arrive as grouped subqueries joined
once.

The three numbers on the envelope are not the same kind of fact. ``teams`` answers the
query; ``serves_any_team`` and ``open_hands_total`` answer the facilitator, and neither
narrows with the restriction.
"""

from datetime import UTC, datetime

from sqlalchemy import func, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.selectable import Subquery

from app.core.enums import ProjectRole
from app.db.models.auth import User
from app.db.models.device import Device
from app.db.models.internalization_room import (
    IRQuestion,
    IRQuestionStatus,
    IRSession,
    IRSessionStatus,
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
from app.services.internalization_room.sessions import DEFAULT_PERICOPE, PANORAMA_PREFIX
from app.services.project.team_restriction import as_work_queue, matching
from app.services.project.team_state import team_state


def _active_passage_subquery() -> Subquery:
    """The team's current passage: the most recent session that names one.

    The panorama is skipped rather than read as a passage. It is material about the *book*
    and plays at the opening of a new one, so a team whose latest session is ``OV-Ruth`` is
    not working on ``OV-Ruth`` — there is no such passage, and the canon refuses to be asked
    for one.
    """
    ranked = (
        select(
            IRSession.project_id.label("project_id"),
            IRSession.pericope.label("pericope"),
            IRSession.status.label("status"),
            func.row_number()
            .over(
                partition_by=IRSession.project_id,
                order_by=(IRSession.created_at.desc(), IRSession.id.desc()),
            )
            .label("place"),
        )
        .where(
            IRSession.project_id.is_not(None),
            ~IRSession.pericope.startswith(PANORAMA_PREFIX),
        )
        .subquery()
    )
    return (
        select(ranked.c.project_id, ranked.c.pericope, ranked.c.status)
        .where(ranked.c.place == 1)
        .subquery()
    )


def _last_activity_subquery() -> Subquery:
    """The last moment the team did anything, across everything it can do.

    All three tables, not just the session's own row: a raised hand does not update the
    session it was asked in, and a count that misses it errs **low**. On a work queue that is
    the worse direction — a facilitator does not go looking for what does not appear.
    """
    moments = union_all(
        select(IRSession.project_id.label("project_id"), IRSession.updated_at.label("at")).where(
            IRSession.project_id.is_not(None)
        ),
        select(IRQuestion.project_id.label("project_id"), IRQuestion.created_at.label("at")).where(
            IRQuestion.project_id.is_not(None)
        ),
        select(IRTake.project_id.label("project_id"), IRTake.created_at.label("at")).where(
            IRTake.project_id.is_not(None)
        ),
    ).subquery()
    return (
        select(moments.c.project_id, func.max(moments.c.at).label("last_activity_at"))
        .group_by(moments.c.project_id)
        .subquery()
    )


def _open_hands_subquery() -> Subquery:
    return (
        select(IRQuestion.project_id.label("project_id"), func.count().label("open_hands"))
        .where(
            IRQuestion.status == IRQuestionStatus.OPEN,
            IRQuestion.project_id.is_not(None),
        )
        .group_by(IRQuestion.project_id)
        .subquery()
    )


def _device_count_subquery() -> Subquery:
    """Linked devices, counted the same way ``list_team_devices`` lists them.

    An unlinked device keeps its ``project_id`` so the row still records where the tablet
    was, which is why the filter has to be repeated rather than assumed: the number beside a
    team and the length of that team's device list are not allowed to disagree.
    """
    return (
        select(Device.project_id.label("project_id"), func.count().label("device_count"))
        .where(Device.unlinked_at.is_(None), Device.project_id.is_not(None))
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
    active = _active_passage_subquery()
    activity = _last_activity_subquery()
    hands = _open_hands_subquery()
    devices = _device_count_subquery()

    query = (
        select(
            Project.id,
            Project.name,
            Language.name.label("mother_tongue"),
            active.c.pericope,
            active.c.status,
            func.coalesce(hands.c.open_hands, 0).label("open_hands"),
            func.coalesce(devices.c.device_count, 0).label("device_count"),
            activity.c.last_activity_at,
        )
        .join(Language, Language.id == Project.language_id)
        .outerjoin(active, active.c.project_id == Project.id)
        .outerjoin(activity, activity.c.project_id == Project.id)
        .outerjoin(hands, hands.c.project_id == Project.id)
        .outerjoin(devices, devices.c.project_id == Project.id)
    )

    if not user.is_platform_admin:
        query = query.where(
            Project.id.in_(
                select(ProjectUserAccess.project_id).where(
                    ProjectUserAccess.user_id == user.id,
                    ProjectUserAccess.role == ProjectRole.FACILITATOR,
                )
            )
        )

    rows = (await db.execute(query)).all()

    every_team = [
        FacilitatorTeamView(
            team_id=row.id,
            name=row.name,
            mother_tongue=row.mother_tongue,
            active_passage=_passage(row.pericope),
            state=team_state(
                passage_done=row.status == IRSessionStatus.DONE,
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


def _passage(pericope: str | None) -> ActivePassageView:
    """The passage by both its names.

    A team with no session yet is on ``P01``: the room resolves a team's next unfinished
    passage when a session opens and starts there with no history, so a card drawn before the
    first session is drawn on the passage that session will be about — not on nothing.

    The reference comes off the canon verbatim and a pericope the canon does not hold raises
    rather than answering blank. A passage the API cannot name is a data fault, and a card
    quietly missing its reference is the kind of fault nobody reports.
    """
    named = pericope or DEFAULT_PERICOPE
    return ActivePassageView(pericope=named, reference=load_map(named).reference)
