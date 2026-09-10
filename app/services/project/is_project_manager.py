from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.org import MemberRole
from app.db.models.project import ProjectUserAccess


async def is_project_manager(db: AsyncSession, user_id: str, project_id: str) -> bool:
    result = await db.execute(
        select(ProjectUserAccess.id)
        .where(
            ProjectUserAccess.project_id == project_id,
            ProjectUserAccess.user_id == user_id,
            ProjectUserAccess.role == MemberRole.MANAGER,
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None
