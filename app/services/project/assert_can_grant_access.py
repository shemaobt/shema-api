from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError
from app.db.models.auth import User
from app.services.project.is_project_manager import is_project_manager


async def assert_can_grant_access(db: AsyncSession, actor: User, project_id: str) -> None:
    if actor.is_platform_admin:
        return
    if not await is_project_manager(db, actor.id, project_id):
        raise AuthorizationError("You must be a manager of this project")
