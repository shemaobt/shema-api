from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.project import Project
from app.services.project.list_managed_project_ids import list_managed_project_ids


async def get_visible_journey_ids(db: AsyncSession, user: User) -> list[str] | None:
    """Owns which journeys an account may read. `None` means "every one of them".

    A journey is a template, but *which* templates exist is Console information.
    The catalog was readable by any authenticated account until OBT-506 put it
    behind `console_guard`; that closed the door on non-operators but still
    handed every manager the whole catalog, while languages, projects and phases
    already answer a manager with their own slice. A manager operates the
    projects they command, so the journeys they may read are the ones those
    projects were assigned.

    Platform admins get `None` rather than every id, so the caller drops the
    filter instead of materialising a list it would not use.
    """
    if user.is_platform_admin:
        return None

    project_ids = await list_managed_project_ids(db, user.id)
    if not project_ids:
        return []

    result = await db.execute(
        select(Project.journey_id)
        .where(Project.id.in_(project_ids), Project.journey_id.is_not(None))
        .distinct()
    )
    return sorted(journey_id for journey_id in result.scalars().all() if journey_id is not None)
