from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.sound_necklace import SnSession


async def get_session(db: AsyncSession, session_id: str) -> SnSession:
    """Fetch a single session by id or raise NotFoundError."""
    result = await db.execute(select(SnSession).where(SnSession.id == session_id))
    session = result.scalar_one_or_none()
    if session is None:
        raise NotFoundError("Session not found")
    return session
