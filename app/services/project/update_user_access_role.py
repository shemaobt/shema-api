from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.db.models.project import ProjectUserAccess
from app.services.user.get_user_by_id import get_user_by_id


async def update_user_access_role(
    db: AsyncSession,
    project_id: str,
    user_id: str,
    role: str,
) -> ProjectUserAccess:
    target = await get_user_by_id(db, user_id)
    if target.is_platform_admin:
        raise ValidationError(
            "Platform admins cannot receive a project role; they already manage every project."
        )
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
