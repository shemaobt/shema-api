from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.db.models.auth import AccessInvite, Role, User
from app.models.resource_request_access import InviteResponse
from app.services.resource_request_access._gate import assert_can_revoke
from app.services.resource_request_access._invite_status import invite_status


async def revoke_invite(db: AsyncSession, actor: User, invite_id: str) -> InviteResponse:
    """Recall a not-yet-accepted invite: Admin only, idempotent on repeat.

    This is what happens to the open door when access is taken away before
    anyone walked through it — the pending invite is closed here, and a later
    accept answers 409. An *accepted* invite is past recalling: the grant it
    produced is the thing to revoke, through ``revoke_access``.
    """
    assert_can_revoke(actor)

    invite = await db.get(AccessInvite, invite_id)
    if not invite:
        raise NotFoundError("Invitation not found.")

    if invite.accepted_at is not None:
        raise ConflictError(
            "This invitation was already accepted; revoke the granted role instead."
        )

    if invite.revoked_at is None:
        invite.revoked_at = datetime.now(UTC)
        invite.revoked_by = actor.id
        await db.commit()
        await db.refresh(invite)

    role = await db.get(Role, invite.role_id)
    return InviteResponse(
        id=invite.id,
        email=invite.email,
        role_key=role.role_key if role else "",
        status=invite_status(invite),
        created_at=invite.created_at,
        expires_at=invite.expires_at,
        created_by=invite.created_by,
    )
