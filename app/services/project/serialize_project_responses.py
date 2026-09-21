from collections.abc import Sequence

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.phase import Phase, ProjectPhase
from app.db.models.project import Project, ProjectUserAccess
from app.models.project import ProjectMemberPreview, ProjectResponse
from app.services.project.count_project_team_sizes import count_project_team_sizes

MEMBERS_PREVIEW_LIMIT = 4


async def serialize_projects(
    db: AsyncSession,
    projects: Sequence[Project],
) -> list[ProjectResponse]:
    project_ids = [p.id for p in projects]
    team_sizes = await count_project_team_sizes(db, project_ids)
    phase_counts = await _phase_counts_by_project(db, project_ids)
    members_preview = await _members_preview_by_project(db, project_ids)
    return [
        ProjectResponse.model_validate(p).model_copy(
            update={
                "team_size": team_sizes.get(p.id, 0),
                "phases_completed": phase_counts.get(p.id, (0, 0))[0],
                "phases_total": phase_counts.get(p.id, (0, 0))[1],
                "members_preview": members_preview.get(p.id, []),
            }
        )
        for p in projects
    ]


async def serialize_project(db: AsyncSession, project: Project) -> ProjectResponse:
    (response,) = await serialize_projects(db, [project])
    return response


async def _phase_counts_by_project(
    db: AsyncSession,
    project_ids: Sequence[str],
) -> dict[str, tuple[int, int]]:
    """How many phases a project has finished, out of how many it has at all.

    The denominator is the project's **journey**, not the rows it has stamped. A project on a
    journey of nine phases that has touched one reads 1/9 from the day it is assigned, which is
    what the card is for; counting `ProjectPhase` rows made it 1/1 and the bar sat full. This is
    the same rule `list_phases_by_projects` follows for the listing (OBT-419).

    A project with no journey keeps the old count, because for it there is no other set to
    measure against. The numerator never changes: only a stamped row can be completed.
    """
    if not project_ids:
        return {}
    stamped = (
        select(
            ProjectPhase.project_id,
            func.sum(case((ProjectPhase.status == "completed", 1), else_=0)).label("completed"),
            func.count().label("total"),
        )
        .where(ProjectPhase.project_id.in_(project_ids))
        .group_by(ProjectPhase.project_id)
    )
    counts = {
        project_id: (int(completed or 0), int(total))
        for project_id, completed, total in (await db.execute(stamped)).all()
    }

    journeys = (
        select(Project.id, func.count(Phase.id))
        .join(Phase, Phase.journey_id == Project.journey_id)
        .where(Project.id.in_(project_ids), Project.journey_id.is_not(None))
        .group_by(Project.id)
    )
    for project_id, journey_total in (await db.execute(journeys)).all():
        completed, _ = counts.get(project_id, (0, 0))
        counts[project_id] = (completed, int(journey_total))
    return counts


async def _members_preview_by_project(
    db: AsyncSession,
    project_ids: Sequence[str],
) -> dict[str, list[ProjectMemberPreview]]:
    if not project_ids:
        return {}
    member_rank = (
        func.row_number()
        .over(
            partition_by=ProjectUserAccess.project_id,
            order_by=(ProjectUserAccess.granted_at.asc(), ProjectUserAccess.id.asc()),
        )
        .label("member_rank")
    )
    ranked = (
        select(
            ProjectUserAccess.project_id.label("project_id"),
            User.id.label("user_id"),
            User.display_name.label("display_name"),
            User.avatar_url.label("avatar_url"),
            member_rank,
        )
        .join(User, ProjectUserAccess.user_id == User.id)
        .where(
            ProjectUserAccess.project_id.in_(project_ids),
            User.is_platform_admin.is_(False),
        )
        .subquery()
    )
    stmt = (
        select(
            ranked.c.project_id,
            ranked.c.user_id,
            ranked.c.display_name,
            ranked.c.avatar_url,
        )
        .where(ranked.c.member_rank <= MEMBERS_PREVIEW_LIMIT)
        .order_by(ranked.c.project_id, ranked.c.member_rank)
    )
    result = await db.execute(stmt)
    previews: dict[str, list[ProjectMemberPreview]] = {}
    for project_id, user_id, display_name, avatar_url in result.all():
        previews.setdefault(project_id, []).append(
            ProjectMemberPreview(
                user_id=user_id,
                display_name=display_name,
                avatar_url=avatar_url,
            )
        )
    return previews
