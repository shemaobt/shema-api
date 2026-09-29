from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.auth import User
from app.db.models.resource_request import RRRequestLink
from app.services.resource_request._links import require_link_admin


async def revoke_request_link(
    db: AsyncSession, link_id: str, user: User, app_key: str, shema_app_key: str
) -> RRRequestLink:
    """Take a request link back — BE-26 (OBT-537), the Admin alone.

    **Idempotent**: revoking a revoked link answers the link as it stands, with its first
    ``revoked_at`` — the moment it was taken back is the one worth keeping. The row is never
    deleted, because the requests that entered by it keep pointing at it.
    """
    await require_link_admin(db, user, app_key, shema_app_key)
    link = await db.get(RRRequestLink, link_id)
    if link is None:
        raise NotFoundError(f"Request link not found: {link_id}")
    if link.revoked_at is None:
        link.revoked_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(link)
    return link
