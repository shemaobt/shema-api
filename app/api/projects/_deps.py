from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError
from app.db.models.auth import User
from app.services import project_service


async def assert_project_access(db: AsyncSession, user: User, project_id: str) -> None:
    if user.is_platform_admin:
        return
    is_manager = await project_service.is_project_manager(db, user.id, project_id)
    if not is_manager:
        raise AuthorizationError("You do not have access to this project")
