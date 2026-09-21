from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_middleware import require_admin_or_manager
from app.core.exceptions import AuthorizationError
from app.db.models.auth import User
from app.services import project_service

console_guard = [Depends(require_admin_or_manager)]


async def assert_project_access(db: AsyncSession, user: User, project_id: str) -> None:
    if user.is_platform_admin:
        return
    allowed = await project_service.can_access_project(db, user.id, project_id)
    if not allowed:
        raise AuthorizationError("You do not have access to this project")
