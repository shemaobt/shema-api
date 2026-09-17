from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import RoleError
from app.db.models.auth import AccessInvite, Role, User, UserAppRole
from app.models.resource_request_access import (
    AccessAssignmentResponse,
    AccessOverviewResponse,
    InviteResponse,
)
from app.services.authorization.get_app_by_key import get_app_by_key
from app.services.resource_request_access._gate import assert_can_grant
from app.services.resource_request_access._invite_status import invite_status


async def list_access(db: AsyncSession, actor: User, app_key: str) -> AccessOverviewResponse:
    """Who holds what, and which invites are still open — FE-30's one call.

    Visible to whoever can concede (Admin and Gestor): granting sensibly
    requires seeing the current state, while the revoke buttons the screen
    draws only work for the Admin — the same asymmetry as the verbs. Accepted
    invites are omitted (they became grants and appear as such); revoked and
    expired ones stay listed with their status, so a recalled or lapsed door
    is visible rather than silently gone.
    """
    await assert_can_grant(db, actor, app_key)

    app = await get_app_by_key(db, app_key)
    if not app:
        raise RoleError("App not found")

    grants_stmt = (
        select(UserAppRole, User.email, User.display_name, Role.role_key)
        .join(User, User.id == UserAppRole.user_id)
        .join(Role, Role.id == UserAppRole.role_id)
        .where(UserAppRole.app_id == app.id, UserAppRole.revoked_at.is_(None))
        .order_by(UserAppRole.granted_at)
    )
    grants = [
        AccessAssignmentResponse(
            user_id=assignment.user_id,
            email=email,
            display_name=display_name,
            role_key=role_key,
            granted_at=assignment.granted_at,
            granted_by=assignment.granted_by,
            revoked_at=assignment.revoked_at,
            revoked_by=assignment.revoked_by,
        )
        for assignment, email, display_name, role_key in (await db.execute(grants_stmt)).all()
    ]

    invites_stmt = (
        select(AccessInvite, Role.role_key)
        .join(Role, Role.id == AccessInvite.role_id)
        .where(AccessInvite.app_id == app.id, AccessInvite.accepted_at.is_(None))
        .order_by(AccessInvite.created_at)
    )
    invites = [
        InviteResponse(
            id=invite.id,
            email=invite.email,
            role_key=role_key,
            status=invite_status(invite),
            created_at=invite.created_at,
            expires_at=invite.expires_at,
            created_by=invite.created_by,
        )
        for invite, role_key in (await db.execute(invites_stmt)).all()
    ]

    return AccessOverviewResponse(grants=grants, invites=invites)
