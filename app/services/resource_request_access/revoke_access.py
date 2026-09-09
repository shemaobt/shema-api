from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_cache import invalidate_roles
from app.core.exceptions import RoleError
from app.db.models.auth import User, UserAppRole
from app.services.authorization.get_app_by_key import get_app_by_key
from app.services.authorization.get_role import get_role
from app.services.resource_request_access._gate import assert_can_revoke


async def revoke_access(
    db: AsyncSession,
    actor: User,
    target_user_id: str,
    app_key: str,
    role_key: str,
) -> UserAppRole:
    """Revoke one active role: Admin only, never their own, with who and when.

    Not a call into the shared ``revoke_role``: that one runs the symmetric
    gate this app rejects, and records only *when* a grant was revoked. This
    writes ``revoked_by`` alongside ``revoked_at``.
    """
    assert_can_revoke(actor)

    if target_user_id == actor.id:
        raise RoleError("You cannot revoke your own role.")

    app = await get_app_by_key(db, app_key)
    if not app:
        raise RoleError("App not found")

    role = await get_role(db, app.id, role_key)
    if not role:
        raise RoleError("Role not found")

    stmt = select(UserAppRole).where(
        UserAppRole.user_id == target_user_id,
        UserAppRole.app_id == app.id,
        UserAppRole.role_id == role.id,
        UserAppRole.revoked_at.is_(None),
    )
    assignment = (await db.execute(stmt)).scalar_one_or_none()
    if not assignment:
        raise RoleError("Active assignment not found")

    assignment.revoked_at = datetime.now(UTC)
    assignment.revoked_by = actor.id
    await db.commit()
    await db.refresh(assignment)
    invalidate_roles(target_user_id)
    return assignment
