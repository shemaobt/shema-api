from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.project import ProjectUserAccess


async def get_member_counts(db: AsyncSession, project_ids: list[str]) -> dict[str, int]:
    """Return {project_id: member_count} for the given projects.

    The join to ``users`` is what keeps platform admins out, the same rows
    ``list_project_user_access`` hides: counting the raw access rows made a card claim a
    member the members page would not show, and a number nobody can reconcile is worse
    than a smaller one. Legacy admin rows still in the table are covered by this, which
    is why the filter is on ``is_platform_admin`` and not on how the row was written.
    """
    if not project_ids:
        return {}
    stmt = (
        select(
            ProjectUserAccess.project_id,
            func.count().label("member_count"),
        )
        .join(User, ProjectUserAccess.user_id == User.id)
        .where(
            ProjectUserAccess.project_id.in_(project_ids),
            User.is_platform_admin.is_(False),
        )
        .group_by(ProjectUserAccess.project_id)
    )
    result = await db.execute(stmt)
    return {row.project_id: row.member_count for row in result.all()}
