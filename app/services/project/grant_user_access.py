from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.project import ProjectUserAccess
from app.services.project.validate_project_role import validate_project_role


async def grant_user_access(
    db: AsyncSession,
    project_id: str,
    user_id: str,
    role: str = "member",
) -> ProjectUserAccess:
    """Link a user to a project. ``role`` has to be one of ``ProjectRole``.

    An existing link is returned untouched, including its role — granting access again is
    not a way to change what someone already is.
    """
    validate_project_role(role)
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
