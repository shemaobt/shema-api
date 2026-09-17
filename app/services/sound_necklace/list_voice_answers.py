"""The recorded answers a session holds.

DORMANT since the 2026-09-01 scope cut — kept deliberately, not by neglect.

The Colar's SPA now ends at the scene and phrase segmentation: no interview, no report, no
artifact. Nothing has called this module since. This is not dead code and not an oversight — it
still runs end to end when called, and the module belongs to the interview package the system that
hosts the interview next will pick up whole. Read ``docs/sound_necklace_interview_package.md``
before changing or removing anything here.
"""

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
