from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.project import ProjectUserAccess


async def get_user_project_access(
    db: AsyncSession, project_id: str, user_id: str
) -> ProjectUserAccess | None:
    stmt = select(ProjectUserAccess).where(
        ProjectUserAccess.project_id == project_id,
        ProjectUserAccess.user_id == user_id,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
