from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.sound_necklace import SnSession


async def release_lock(db: AsyncSession, session: SnSession, user_id: str) -> None:
    """Drop the caller's lease. Idempotent, and only ever the caller's own.

    Releasing something the caller does not hold — because it lapsed, because another
    tab took it, because it was never held — is a no-op rather than an error: the SPA
    releases on unload and cannot do anything useful with a failure at that point.

    The holder check lives in the WHERE, so idempotent never means "anyone can unlock":
    a stale tab's release matches nothing and leaves the current holder alone.
    """
    await db.execute(
        update(SnSession)
        .where(SnSession.id == session.id, SnSession.locked_by == user_id)
        .values(locked_by=None, lock_expires_at=None)
        .execution_options(synchronize_session=False)
    )
    await db.commit()
