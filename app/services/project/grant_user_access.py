from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.db.models.project import ProjectUserAccess
from app.services.user.get_user_by_id import get_user_by_id


async def grant_user_access(
    db: AsyncSession,
    project_id: str,
    user_id: str,
    role: str = "member",
) -> ProjectUserAccess:
    target = await get_user_by_id(db, user_id)
    if target.is_platform_admin:
        raise ValidationError(
            "Platform admins cannot be added to a project; they already manage every project."
        )
    existing: Select[tuple[ProjectUserAccess]] = select(ProjectUserAccess).where(
        ProjectUserAccess.project_id == project_id,
        ProjectUserAccess.user_id == user_id,
    )
    result = await db.execute(existing)
    existing_access = result.scalar_one_or_none()
    if existing_access:
        return existing_access
    access = ProjectUserAccess(project_id=project_id, user_id=user_id, role=role)
    db.add(access)
    await db.commit()
    await db.refresh(access)
    return access
