from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ProjectRole
from app.db.models.auth import User
from app.db.models.project import Project, ProjectUserAccess


async def list_facilitated_project_ids(db: AsyncSession, user: User) -> set[str]:
    """Every project this user facilitates.

    Narrower than ``can_access_project`` on purpose, and the difference is the point of
    this function: access says yes to a project member, to a project manager, and to
    anyone who reaches the project through an organization. None of those is a
    facilitator. Only a ``project_user_access`` row saying so is.

    An empty set is a valid answer, not an error. It is what a facilitator who has not
    been assigned a team yet gets, and the Desk renders its "talk to administration"
    screen from exactly that.

    A platform admin facilitates everything. They already hold every other power in this
    system, and scoping them to nothing would leave the one person able to investigate a
    room unable to see any room at all.
    """
    if user.is_platform_admin:
        rows = await db.execute(select(Project.id))
        return set(rows.scalars().all())

    rows = await db.execute(
        select(ProjectUserAccess.project_id).where(
            ProjectUserAccess.user_id == user.id,
            ProjectUserAccess.role == ProjectRole.FACILITATOR,
        )
    )
    return set(rows.scalars().all())
