from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError, RoleError
from app.db.models.auth import AccessInvite, App, Role, User
from app.models.resource_request_access import AccessGrantResponse
from app.services.auth.hash_refresh_token import hash_refresh_token
from app.services.authorization.grant_app_role import grant_app_role
from app.services.resource_request_access._invite_status import invite_status
from app.services.resource_request_access._rules import assert_role_compatible


async def accept_invite(db: AsyncSession, actor: User, raw_token: str) -> AccessGrantResponse:
    """Consume a live invite and grant its role to the signed-in holder.

    The grant and the consumption commit together: an invite is never spent
    without its role landing, and a role never lands off a still-spendable
    invite. ``granted_by`` is the inviter, not the acceptor — the concession
    was theirs, and the audit trail should say so. Exclusivity is checked here
    and not only at creation, because the holder's roles may have changed in
    the days between the letter and the click.
    """
    token_hash = hash_refresh_token(raw_token)
    stmt = select(AccessInvite).where(AccessInvite.token_hash == token_hash)
    invite = (await db.execute(stmt)).scalar_one_or_none()
    if not invite:
        raise NotFoundError("Invitation not found.")

    status = invite_status(invite)
    if status == "revoked":
        raise ConflictError("This invitation has been revoked.")
    if status == "used":
        raise ConflictError("This invitation has already been used.")
    if status == "expired":
        raise ConflictError("This invitation has expired.")

    if actor.email.lower() != invite.email:
        raise AuthorizationError("This invitation was issued to a different e-mail address.")

    app = await db.get(App, invite.app_id)
    role = await db.get(Role, invite.role_id)
    if not app or not role:
        raise RoleError("The application or role behind this invitation no longer exists.")

    await assert_role_compatible(db, actor.id, app.id, role.role_key)

    assignment = await grant_app_role(
        db,
        actor.id,
        app.app_key,
        role.role_key,
        granted_by=invite.created_by,
        commit=False,
    )
    invite.accepted_at = datetime.now(UTC)
    invite.accepted_by = actor.id
    await db.commit()
    await db.refresh(assignment)
    return AccessGrantResponse(
        user_id=assignment.user_id,
        role_key=role.role_key,
        granted_at=assignment.granted_at,
        granted_by=assignment.granted_by,
        revoked_at=assignment.revoked_at,
        revoked_by=assignment.revoked_by,
    )
