from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.sound_necklace import SnVoiceAnswer


async def list_voice_answers(db: AsyncSession, session_id: str) -> list[SnVoiceAnswer]:
    """Every answer recorded for a session, ordered by path.

    This is what the Mapeamento screen reads to know which questions are answered — the
    reason the answers are a table and not just a bucket prefix.
    """
    result = await db.execute(
        select(SnVoiceAnswer)
        .where(SnVoiceAnswer.session_id == session_id)
        .order_by(SnVoiceAnswer.resource_path)
    )
    return list(result.scalars().all())
