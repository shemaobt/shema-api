from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.org import MemberRole
from app.db.models.project import ProjectUserAccess


async def get_managed_project_ids(db: AsyncSession, user_id: str) -> list[str]:
    result = await db.execute(
        select(ProjectUserAccess.project_id).where(
            ProjectUserAccess.user_id == user_id,
            ProjectUserAccess.role == MemberRole.MANAGER,
        )
    )
    return sorted(result.scalars().all())
