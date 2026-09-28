"""``GET /access/invites`` — the invitations of the two apps nobody has accepted yet.

Pending, expired and revoked alike, newest first, with their regions: a lapsed or recalled
door stays visible rather than silently gone, and an accepted one is read as the grant it
became. Both apps' invites are listed, including those the form's own door wrote — the Admin
recalls in both. Capped, because the table only grows.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shema_grant import OpenInvite
from app.services.resource_request_access._invite_status import invite_status
from app.services.resource_request_access.invite_store import InviteRow, find_invites
from app.services.shema._grant_rules import GrantApps

#: How many invitations one read returns.
DEFAULT_LIMIT = 200


def open_invite(row: InviteRow) -> OpenInvite:
    """One invite on the wire — the shape every invitation route of the surface answers."""
    invite = row.invite
    return OpenInvite(
        id=invite.id,
        email=invite.email,
        appKey=row.app_key,
        roleKey=row.role_key,
        regionKeys=list(invite.region_keys or []),
        status=invite_status(invite),
        createdAt=invite.created_at,
        expiresAt=invite.expires_at,
        createdBy=invite.created_by,
    )


async def list_invites(
    db: AsyncSession, apps: GrantApps, *, limit: int = DEFAULT_LIMIT
) -> list[OpenInvite]:
    """The newest ``limit`` invitations of both apps that nobody accepted."""
    rows = await find_invites(db, apps, newest_first=True, limit=limit)
    return [open_invite(row) for row in rows]
