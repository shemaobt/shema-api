from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.project import Project


async def list_projects_by_ids(db: AsyncSession, project_ids: list[str]) -> list[Project]:
    if not project_ids:
        return []
    stmt = select(Project).where(Project.id.in_(project_ids)).order_by(Project.name)
    result = await db.execute(stmt)
    return list(result.scalars().unique().all())
