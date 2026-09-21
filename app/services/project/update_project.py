from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.db.models.project import Project
from app.services.language.get_language_by_id import get_language_by_id
from app.services.project.get_project_or_404 import get_project_or_404


async def update_project(
    db: AsyncSession,
    project_id: str,
    *,
    name: str | None = None,
    description: str | None = None,
    language_id: str | None = None,
) -> Project:
    project = await get_project_or_404(db, project_id)
    if language_id is not None:
        language = await get_language_by_id(db, language_id)
        if not language:
            raise NotFoundError("Language not found")
        if not language.is_active:
            raise ValidationError("Language is not active")
        project.language_id = language_id
    if name is not None:
        project.name = name
    if description is not None:
        project.description = description
    await db.commit()
    await db.refresh(project)
    return project
