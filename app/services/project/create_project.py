from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.project import Project
from app.services.project.grant_user_access import grant_user_access
from app.services.user.get_user_by_id import get_user_by_id


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
        creator = await get_user_by_id(db, creator_user_id)
        if not creator.is_platform_admin:
            await grant_user_access(db, project.id, creator_user_id, role="manager")

    return project
