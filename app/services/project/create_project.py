from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.project import Project
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
    from app.services.phase.attach_all_phases_to_project import attach_all_phases_to_project

    project = Project(
        name=name,
        language_id=language_id,
        description=description,
        latitude=latitude,
        longitude=longitude,
        location_display_name=location_display_name,
    )
    db.add(project)
    await db.flush()
    await attach_all_phases_to_project(db, project.id)
    await db.commit()
    await db.refresh(project)

    if creator_user_id:
        await grant_user_access(db, project.id, creator_user_id, role="manager")

    return project
