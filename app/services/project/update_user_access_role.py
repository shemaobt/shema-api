from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.project import ProjectUserAccess
from app.services.project.validate_project_role import validate_project_role


async def update_user_access_role(
    db: AsyncSession,
    project_id: str,
    user_id: str,
    role: str,
) -> ProjectUserAccess:
    """Change what a user is on a project. ``role`` has to be one of ``ProjectRole``."""
    validate_project_role(role)
    stmt = select(ProjectUserAccess).where(
        ProjectUserAccess.project_id == project_id,
        ProjectUserAccess.user_id == user_id,
    )
    result = await db.execute(stmt)
    access = result.scalar_one_or_none()
    if not access:
        raise NotFoundError("User access not found for this project")
    access.role = role
    await db.commit()
    await db.refresh(access)
    return access
