from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.project import Project
from app.services.language.get_language_or_404 import get_language_or_404


async def get_language_stats(db: AsyncSession, language_id: str) -> list[tuple[str, str]]:
    await get_language_or_404(db, language_id)
    stmt = (
        select(Project.id, Project.name)
        .where(Project.language_id == language_id)
        .order_by(Project.name)
    )
    result = await db.execute(stmt)
    return [(row.id, row.name) for row in result.all()]
