from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.project import ProjectUserAccess


async def list_project_user_access(
    db: AsyncSession,
    project_id: str,
) -> list[tuple[ProjectUserAccess, User]]:
    stmt: Select[tuple[ProjectUserAccess, User]] = (
        select(ProjectUserAccess, User)
        .join(User, ProjectUserAccess.user_id == User.id)
        .where(
            ProjectUserAccess.project_id == project_id,
            User.is_platform_admin.is_(False),
        )
        .order_by(ProjectUserAccess.granted_at)
    )
    result = await db.execute(stmt)
    return [row._tuple() for row in result.all()]
