from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ProjectRole
from app.core.exceptions import AuthorizationError, NotFoundError
from app.db.models.auth import User
from app.services.project.get_user_project_access import get_user_project_access
from app.services.project.is_project_manager import is_project_manager


async def assert_can_modify_member_role(
    db: AsyncSession, actor: User, project_id: str, target_user_id: str
) -> None:
    """A platform admin touches anyone; a project manager touches only plain members.

    Another manager is off limits, and so is any other role — a facilitator is granted by
    the administration, outside the product, and the manager has no say over it.
    """
    if actor.is_platform_admin:
        return
    if not await is_project_manager(db, actor.id, project_id):
        raise AuthorizationError("You must be a manager of this project")
    target = await get_user_project_access(db, project_id, target_user_id)
    if target is None:
        raise NotFoundError("User access not found for this project")
    if target.role == ProjectRole.MANAGER:
        raise AuthorizationError("Managers cannot change or remove another manager")
    if target.role != ProjectRole.MEMBER:
        raise AuthorizationError(f"Managers cannot change or remove a {target.role}, only members")
