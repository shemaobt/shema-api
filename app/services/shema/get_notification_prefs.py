"""One account's notification settings, or the honest default when nothing was ever saved.

The row is created by :func:`~app.services.shema.save_notification_prefs.save_notification_prefs`
on the first write, never by a read: a ``GET`` before anybody has opened the preferences screen
answers the column defaults (``app/db/models/shema_notification.py`` — enabled, every channel
off, both addresses empty) without minting a row nobody asked for.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.shema_notification import ShemaNotificationPrefs
from app.models.shema_notification import ShemaNotificationPrefsOut


async def get_notification_prefs(db: AsyncSession, user_id: str) -> ShemaNotificationPrefsOut:
    """This account's preferences, or the default shape if none were ever saved."""
    row = await db.get(ShemaNotificationPrefs, user_id)
    return ShemaNotificationPrefsOut.default() if row is None else ShemaNotificationPrefsOut.of(row)
