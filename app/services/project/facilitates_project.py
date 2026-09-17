from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ProjectRole
from app.db.models.auth import User
from app.db.models.project import ProjectUserAccess


async def facilitates_project(db: AsyncSession, user: User, project_id: str) -> bool:
    """Whether this user facilitates this one team.

    The single question every facilitator route asks. It replaces ``can_access_project``
    on those routes and does not change it for anyone else — the other apps in this
    codebase mean the broader thing by "access" and still do.
    """
    if user.is_platform_admin:
        return True

    found = await db.execute(
        select(ProjectUserAccess.id)
        .where(
            ProjectUserAccess.project_id == project_id,
            ProjectUserAccess.user_id == user.id,
            ProjectUserAccess.role == ProjectRole.FACILITATOR,
        )
        .limit(1)
    )
    return found.scalar_one_or_none() is not None
