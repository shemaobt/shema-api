from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ProjectRole
from app.core.exceptions import AuthorizationError
from app.db.models.auth import User
from app.services.project.is_project_manager import is_project_manager


async def assert_can_grant_access(
    db: AsyncSession, actor: User, project_id: str, role: str
) -> None:
    """A platform admin grants any role; a project manager only a member or a manager.

    The ceiling is the one ``assert_can_modify_member_role`` already enforces: a manager
    allowed to hand out a facilitator would then be refused the change and the revoke of
    the row just written. A facilitator is granted by the administration, outside the
    product.
    """
    if actor.is_platform_admin:
        return
    if not await is_project_manager(db, actor.id, project_id):
        raise AuthorizationError("You must be a manager of this project")
    if role not in (ProjectRole.MEMBER, ProjectRole.MANAGER):
        raise AuthorizationError(f"Managers cannot grant a {role}, only members and managers")
