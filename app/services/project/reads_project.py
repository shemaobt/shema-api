from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.services.project.facilitated_scope import reads_every_team
from app.services.project.facilitates_project import facilitates_project


async def reads_project(db: AsyncSession, user: User, project_id: str) -> bool:
    """Whether this user may read this one team: every read route asks this, never a write.

    A consultant reads every team (ADR 0058); anyone else reads the teams they facilitate.
    """
    return await reads_every_team(db, user) or await facilitates_project(db, user, project_id)
