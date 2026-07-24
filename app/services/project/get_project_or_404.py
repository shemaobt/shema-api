from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.project import Project
from app.services.common import get_or_raise


async def get_project_or_404(
    db: AsyncSession, project_id: str, *, for_update: bool = False
) -> Project:
    return await get_or_raise(db, Project, project_id, label="Project", for_update=for_update)
