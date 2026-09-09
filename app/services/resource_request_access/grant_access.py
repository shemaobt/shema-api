from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import RoleError, UnknownReferenceError
from app.db.models.auth import User, UserAppRole
from app.services.auth.get_user_by_id import get_user_by_id
from app.services.authorization.get_app_by_key import get_app_by_key
from app.services.authorization.grant_app_role import grant_app_role
from app.services.resource_request_access._gate import assert_can_grant
from app.services.resource_request_access._rules import assert_role_compatible


async def grant_access(
    db: AsyncSession,
    actor: User,
    target_user_id: str,
    app_key: str,
    role_key: str,
) -> UserAppRole:
    """Name a user into a role: Admin and Gestor concede, never to themselves.

    Enforces the mesa/gestor exclusivity before delegating the write to
    ``grant_app_role``, which records ``granted_by`` and ``granted_at``.
    """
    await assert_can_grant(db, actor, app_key)

    if target_user_id == actor.id:
        raise RoleError("You cannot grant a role to yourself.")

    target = await get_user_by_id(db, target_user_id)
    if not target:
        raise UnknownReferenceError("Target user not found.")

    app = await get_app_by_key(db, app_key)
    if not app:
        raise RoleError("App not found")

    await assert_role_compatible(db, target_user_id, app.id, role_key)

    return await grant_app_role(db, target_user_id, app_key, role_key, granted_by=actor.id)
