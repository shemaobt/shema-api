from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.sound_necklace import SnAudioRef


async def get_audio_project_id(db: AsyncSession, audio_id: str) -> str:
    """The project an audio belongs to, or a miss.

    This is what the project gate stands on: an acousteme artifact has no project of
    its own, so an audio no ref claims is one this API never offered — a miss, not a
    forbidden.
    """
    result = await db.execute(select(SnAudioRef.project_id).where(SnAudioRef.audio_id == audio_id))
    project_id = result.scalar_one_or_none()
    if project_id is None:
        raise NotFoundError("Audio not found")
    return str(project_id)
