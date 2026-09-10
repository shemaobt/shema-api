from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.project import ProjectUserAccess


async def count_project_team_sizes(db: AsyncSession, project_ids: list[str]) -> dict[str, int]:
    if not project_ids:
        return {}
    stmt = (
        select(
            ProjectUserAccess.project_id,
            func.count(distinct(ProjectUserAccess.user_id)),
        )
        .where(ProjectUserAccess.project_id.in_(project_ids))
        .group_by(ProjectUserAccess.project_id)
    )
    result = await db.execute(stmt)
    counts: dict[str, int] = {row[0]: row[1] for row in result.all()}
    return {project_id: counts.get(project_id, 0) for project_id in project_ids}
