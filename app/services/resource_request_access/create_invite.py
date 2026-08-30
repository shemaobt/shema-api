import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ConflictError, RoleError
from app.db.models.auth import AccessInvite, User
from app.services.auth.hash_refresh_token import hash_refresh_token
from app.services.authorization.get_app_by_key import get_app_by_key
from app.services.authorization.get_role import get_role
from app.services.common.email import send_access_invite_email
from app.services.resource_request_access._gate import assert_can_grant


async def create_invite(
    db: AsyncSession,
    actor: User,
    app_key: str,
    email: str,
    role_key: str,
) -> tuple[AccessInvite, str]:
    """Write a single-use invite and mail its link; returns (invite, invite_url).

    The row is committed before the letter leaves and sending is best-effort,
    so a dead provider cannot roll the invite back — and the returned URL lets
    the creator hand the link over some other way when that happens. Only the
    token's SHA-256 is stored; the raw token lives in the URL alone. Inviting
    your own e-mail is refused as the self-grant it would become, and a second
    pending invite for the same e-mail and role is refused as a duplicate.
    """
    await assert_can_grant(db, actor, app_key)

    normalized_email = email.strip().lower()
    if not normalized_email:
        raise RoleError("An e-mail address is required.")
    if normalized_email == actor.email.lower():
        raise RoleError("You cannot invite yourself.")

    app = await get_app_by_key(db, app_key)
    if not app:
        raise RoleError("App not found")

    role = await get_role(db, app.id, role_key)
    if not role:
        raise RoleError("Role not found")

    now = datetime.now(UTC)
    stmt = select(AccessInvite.id).where(
        AccessInvite.app_id == app.id,
        AccessInvite.role_id == role.id,
        AccessInvite.email == normalized_email,
        AccessInvite.accepted_at.is_(None),
        AccessInvite.revoked_at.is_(None),
        AccessInvite.expires_at > now,
    )
    if (await db.execute(stmt)).scalar_one_or_none():
        raise ConflictError("An invitation for this e-mail and role is already pending.")

    raw_token = secrets.token_hex(32)
    settings = get_settings()
    invite = AccessInvite(
        app_id=app.id,
        role_id=role.id,
        email=normalized_email,
        token_hash=hash_refresh_token(raw_token),
        expires_at=now + timedelta(days=settings.access_invite_expire_days),
        created_by=actor.id,
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)

    base_url = app.app_url.rstrip("/") if app.app_url else "http://localhost:5173"
    invite_url = f"{base_url}/invite?token={raw_token}"

    await send_access_invite_email(
        to_email=normalized_email,
        inviter_name=actor.display_name,
        invite_url=invite_url,
        app_name=app.name,
    )
    return invite, invite_url
