from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.sound_necklace import SnVoiceAnswer
from app.services.oral_collector import gcs_utils
from app.services.sound_necklace.constants import GCS_SN_BUCKET


async def delete_voice_answer(db: AsyncSession, session_id: str, resource_path: str) -> None:
    """Remove one voice answer — the object and its row.

    A path that was never recorded is not an error: the caller's goal (no answer at this
    path) is already met, so deleting a missing answer is a no-op.

    The object is deleted before the row, deliberately. If the commit then fails, the row
    survives pointing at a now-missing object — a playback that 404s until a retry heals
    it. That is the safe direction to fail for LGPD-sensitive audio: better a dangling
    pointer than the reverse, a deleted row and the recording still sitting in the bucket
    with nothing left to reach it.
    """
    answer = await db.get(SnVoiceAnswer, (session_id, resource_path))
    if answer is None:
        return

    await gcs_utils.delete_gcs_object(GCS_SN_BUCKET, answer.storage_key)
    await db.delete(answer)
    await db.commit()
