from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.models.resource_request_access import InviteResponse
from app.services.resource_request_access._gate import assert_can_revoke
from app.services.resource_request_access._invite_status import invite_status
from app.services.resource_request_access.invite_store import find_invite, recall_invite


async def revoke_invite(db: AsyncSession, actor: User, invite_id: str) -> InviteResponse:
    """Recall a not-yet-accepted invite: Admin only, idempotent on repeat.

    This is what happens to the open door when access is taken away before
    anyone walked through it — the pending invite is closed here, and a later
    accept answers 409. An *accepted* invite is past recalling: the grant it
    produced is the thing to revoke, through ``revoke_access``.
    """
    assert_can_revoke(actor)

    found = await find_invite(db, invite_id)
    invite = await recall_invite(db, actor, found.invite)
    return InviteResponse(
        id=invite.id,
        email=invite.email,
        role_key=found.role_key,
        status=invite_status(invite),
        created_at=invite.created_at,
        expires_at=invite.expires_at,
        created_by=invite.created_by,
    )
