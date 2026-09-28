from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.models.resource_request_access import InviteCreatedResponse
from app.services.common.email import send_access_invite_email
from app.services.resource_request_access._gate import assert_can_grant
from app.services.resource_request_access._invite_status import invite_status
from app.services.resource_request_access._rules import assert_role_grantable
from app.services.resource_request_access.invite_store import invite_link, issue_invite


async def create_invite(
    db: AsyncSession,
    actor: User,
    app_key: str,
    email: str,
    role_key: str,
) -> InviteCreatedResponse:
    """Write a single-use invite and mail its link; the answer carries the link.

    The row is committed before the letter leaves and sending is best-effort,
    so a dead provider cannot roll the invite back — and the returned URL lets
    the creator hand the link over some other way when that happens. Only the
    token's SHA-256 is stored; the raw token lives in the URL alone. Inviting
    your own e-mail is refused as the self-grant it would become, a second
    pending invite for the same e-mail and role is refused as a duplicate, and
    only an installation admin invites anyone to the ``admin`` role.

    This door's gate, then the invite itself from ``invite_store``, which the
    Shemá Admin's surface composes behind its own gate (OBT-543).
    """
    await assert_can_grant(db, actor, app_key)
    assert_role_grantable(actor, role_key)

    issued = await issue_invite(db, actor, app_key, email, role_key)
    invite = issued.invite
    invite_url = invite_link(issued.app, issued.raw_token)

    await send_access_invite_email(
        to_email=invite.email,
        inviter_name=actor.display_name,
        invite_url=invite_url,
        app_name=issued.app.name,
    )
    return InviteCreatedResponse(
        id=invite.id,
        email=invite.email,
        role_key=issued.role.role_key,
        status=invite_status(invite),
        created_at=invite.created_at,
        expires_at=invite.expires_at,
        created_by=invite.created_by,
        invite_url=invite_url,
    )
