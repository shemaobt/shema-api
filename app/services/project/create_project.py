from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.db.models.project import Project
from app.services.language.get_language_by_id import get_language_by_id
from app.services.project.grant_user_access import grant_user_access


async def create_project(
    db: AsyncSession,
    name: str,
    language_id: str,
    description: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    location_display_name: str | None = None,
    creator_user_id: str | None = None,
) -> Project:
    language = await get_language_by_id(db, language_id)
    if not language:
        raise NotFoundError("Language not found")
    if not language.is_active:
        raise ValidationError("Language is not active")
    project = Project(
        name=name,
        language_id=language_id,
        description=description,
        latitude=latitude,
        longitude=longitude,
        location_display_name=location_display_name,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)

    if creator_user_id:
        await grant_user_access(db, project.id, creator_user_id, role="manager")

    return project
