from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.sound_necklace import SnConsent


async def list_consents(db: AsyncSession, session_id: str) -> list[SnConsent]:
    """Every consent recorded for a session, ordered by type.

    A session with no record is not an error: it is a session for which no consent was
    given, and an empty list is what says so.
    """
    result = await db.execute(
        select(SnConsent).where(SnConsent.session_id == session_id).order_by(SnConsent.type)
    )
    return list(result.scalars().all())
