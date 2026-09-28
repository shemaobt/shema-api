from datetime import UTC, datetime

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_cache import invalidate_roles
from app.core.exceptions import RoleError
from app.db.models.auth import User, UserAppRole
from app.services.authorization.assert_can_manage_roles import assert_can_manage_roles
from app.services.authorization.get_app_by_key import get_app_by_key
from app.services.authorization.get_role import get_role


async def revoke_role(
    db: AsyncSession,
    actor_user: User,
    target_user_id: str,
    app_key: str,
    role_key: str,
    *,
    commit: bool = True,
) -> UserAppRole:
    """Revoke a live role, recording who revoked it and when.

    **Every live row of the grant is revoked, not one.** ``user_app_roles`` has no unique
    constraint on a live ``(user, app, role)`` and ``grant_app_role`` checks before it
    inserts, so two requests landing together can leave two live rows; reading one of them
    here used to raise ``MultipleResultsFound`` and answer 500, and revoking one would have
    left the role held. The first row is returned, which is all the callers read.

    ``revoked_by`` is written beside ``revoked_at``, so a revocation has an author in the
    history the Shemá Admin reads (OBT-543). ``commit=False`` flushes and leaves the
    transaction to the caller, as ``grant_app_role`` does.
    """
    await assert_can_manage_roles(db, actor_user, app_key)

    app = await get_app_by_key(db, app_key)
    if not app:
        raise RoleError("App not found")

    role = await get_role(db, app.id, role_key)
    if not role:
        raise RoleError("Role not found")

    stmt: Select[tuple[UserAppRole]] = select(UserAppRole).where(
        UserAppRole.user_id == target_user_id,
        UserAppRole.app_id == app.id,
        UserAppRole.role_id == role.id,
        UserAppRole.revoked_at.is_(None),
    )
    assignments = list((await db.execute(stmt)).scalars().all())
    if not assignments:
        raise RoleError("Active assignment not found")

    now = datetime.now(UTC)
    for assignment in assignments:
        assignment.revoked_at = now
        assignment.revoked_by = actor_user.id
    if commit:
        await db.commit()
        await db.refresh(assignments[0])
    else:
        await db.flush()
    invalidate_roles(target_user_id)
    return assignments[0]
