from collections.abc import Collection

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.notification import Notification


async def list_notifications(
    db: AsyncSession,
    user_id: str,
    app_id: str,
    *,
    unread_only: bool = False,
    limit: int = 50,
    exclude_event_types: Collection[str] = (),
) -> list[Notification]:

    stmt = select(Notification).where(
        Notification.user_id == user_id,
        Notification.app_id == app_id,
    )
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    if exclude_event_types:
        stmt = stmt.where(Notification.event_type.not_in(exclude_event_types))
    stmt = stmt.order_by(Notification.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())
