from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.resource_request import RRRequestLink
from app.services.resource_request._links import require_link_admin


async def list_request_links(
    db: AsyncSession, user: User, app_key: str, shema_app_key: str
) -> list[RRRequestLink]:
    """Every request link, newest first — the Admin's list (BE-26, OBT-537).

    Revoked and expired links stay listed: the list is where the Admin sees what was issued,
    and a link that silently disappeared would read as one never sent.
    """
    await require_link_admin(db, user, app_key, shema_app_key)
    rows = await db.execute(select(RRRequestLink).order_by(RRRequestLink.created_at.desc()))
    return list(rows.scalars().all())
