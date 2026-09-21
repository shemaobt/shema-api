from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.project import ProjectUserAccess


async def get_manager_user_ids(db: AsyncSession, user_ids: list[str] | None = None) -> set[str]:
    stmt: Select[tuple[str]] = (
        select(ProjectUserAccess.user_id).where(ProjectUserAccess.role == "manager").distinct()
    )
    if user_ids is not None:
        stmt = stmt.where(ProjectUserAccess.user_id.in_(user_ids))
    result = await db.execute(stmt)
    return set(result.scalars().all())
