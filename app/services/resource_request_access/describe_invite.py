from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.auth import AccessInvite, App, Role, User
from app.models.resource_request_access import InviteDescriptionResponse
from app.services.auth.hash_refresh_token import hash_refresh_token
from app.services.resource_request_access._invite_status import invite_status


async def describe_invite(db: AsyncSession, raw_token: str) -> InviteDescriptionResponse:
    """Answer an anonymous link-holder: is this invite live, and do they have an account.

    This is the public endpoint's whole content, deliberately thin: enough for
    the front to route the person — ``account_exists`` False sends them to
    signup, True to login — and to say plainly when a link is expired, used or
    revoked. It never grants anything and never returns the token back.
    """
    token_hash = hash_refresh_token(raw_token)
    stmt = select(AccessInvite).where(AccessInvite.token_hash == token_hash)
    invite = (await db.execute(stmt)).scalar_one_or_none()
    if not invite:
        raise NotFoundError("Invitation not found.")

    app = await db.get(App, invite.app_id)
    role = await db.get(Role, invite.role_id)

    account_stmt = select(User.id).where(User.email == invite.email, User.is_active.is_(True))
    account_exists = (await db.execute(account_stmt)).scalar_one_or_none() is not None

    return InviteDescriptionResponse(
        status=invite_status(invite),
        email=invite.email,
        app_name=app.name if app else "",
        role_key=role.role_key if role else "",
        role_label=role.label if role else "",
        account_exists=account_exists,
    )
