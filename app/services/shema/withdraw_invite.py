"""``POST /access/invites/revoke`` — the Admin recalls an invitation before it is accepted.

Only the two apps' invitations: any other reads as not found, so the route cannot tell
whether some other application's invite exists. An accepted one is past recalling (409);
recalling twice is a no-op.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.models.shema_grant import OpenInvite
from app.services.resource_request_access.invite_store import (
    InviteRow,
    find_invite,
    recall_invite,
)
from app.services.shema._grant_rules import GrantApps, require_admin_in
from app.services.shema.list_invites import open_invite


async def withdraw_invite(
    db: AsyncSession, apps: GrantApps, *, invite_id: str, actor: User
) -> OpenInvite:
    """Close the invitation and answer it as it now reads."""
    found = await find_invite(db, invite_id, app_keys=apps)
    await require_admin_in(db, actor, (found.app_key,))
    invite = await recall_invite(db, actor, found.invite)
    return open_invite(InviteRow(invite, found.app_key, found.role_key))
