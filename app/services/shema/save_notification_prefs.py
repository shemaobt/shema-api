"""Writing one account's notification settings — the one write this module's panel needs.

FE-38 built the screen against ``PUT /notifications/prefs`` (FE-44 §9.11, §10); this is the
whole of what it calls. One row per account, created on the first save and overwritten on every
one after, because there is nothing to have two of. **No channel here is ever turned into a
send** — ``docs/shema.md`` §4.6 measured that no e-mail, push or WhatsApp sender exists in
``app/services/notifications/``, so a preference recorded today has nothing behind it yet, and
that is the honest state to ship rather than a half-wired one.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.shema_notification import ShemaNotificationPrefs
from app.models.shema_notification import ShemaNotificationPrefsIn, ShemaNotificationPrefsOut


async def save_notification_prefs(
    db: AsyncSession, user_id: str, payload: ShemaNotificationPrefsIn
) -> ShemaNotificationPrefsOut:
    """Upsert this account's row and answer it back, the way every save in this module does."""
    row = await db.get(ShemaNotificationPrefs, user_id)
    if row is None:
        row = ShemaNotificationPrefs(user_id=user_id)
        db.add(row)

    row.enabled = payload.enabled
    row.channel_email = payload.channels.email
    row.channel_push = payload.channels.push
    row.channel_whatsapp = payload.channels.whatsapp
    row.when_key = payload.when
    row.scope_key = payload.scope
    row.email_addr = payload.email_addr
    row.phone_addr = payload.phone_addr
    row.custom_project_ids = list(payload.custom_project_ids)

    await db.commit()
    await db.refresh(row)
    return ShemaNotificationPrefsOut.of(row)
