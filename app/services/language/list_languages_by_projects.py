from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.language import Language
from app.db.models.project import Project


async def list_languages_by_projects(db: AsyncSession, project_ids: list[str]) -> list[Language]:
    if not project_ids:
        return []
    language_ids_subq = select(Project.language_id).where(Project.id.in_(project_ids)).distinct()
    stmt = select(Language).where(Language.id.in_(language_ids_subq)).order_by(Language.code)
    result = await db.execute(stmt)
    return list(result.scalars().all())
