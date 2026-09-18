from collections.abc import Sequence

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.phase import ProjectPhase
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
    if not project_ids:
        return {}
    stmt = (
        select(
            ProjectPhase.project_id,
            func.sum(case((ProjectPhase.status == "completed", 1), else_=0)),
            func.count(),
        )
        .where(ProjectPhase.project_id.in_(project_ids))
        .group_by(ProjectPhase.project_id)
    )
    result = await db.execute(stmt)
    return {
        project_id: (int(completed or 0), int(total))
        for project_id, completed, total in result.all()
    }


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
