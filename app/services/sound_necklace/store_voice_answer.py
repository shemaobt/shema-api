from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.db.models.sound_necklace import SnVoiceAnswer
from app.services.oral_collector import gcs_utils
from app.services.sound_necklace.constants import GCS_SN_BUCKET, VOICE_ANSWER_CONTENT_TYPE


def _storage_key(session_id: str, resource_path: str) -> str:
    """Where one answer's bytes live.

    The resource path is used verbatim as the object-name suffix — safe because it was
    validated against the fixed allowlist before it got here, so it is one of exactly
    three shapes and can contain no traversal and no free-form segment.
    """
    return f"sound-necklace/{session_id}/{resource_path}"


async def store_voice_answer(
    db: AsyncSession, session_id: str, resource_path: str, data: bytes
) -> SnVoiceAnswer:
    """Store one voice answer, replacing any previous take of the same question (O5).

    The bytes are opaque audio: they are moved to the private bucket and never parsed.
    Re-recording overwrites in place — the key is a pure function of session+path, so a
    second take lands on the same object and updates the one row.

    The size cap is the router's job (it raises 413 from the body before this is
    called). The empty check stays here as the one size rule every caller shares,
    including a future non-HTTP one that has no router in front of it.
    """
    if not data:
        raise ValidationError("The voice answer is empty")

    key = _storage_key(session_id, resource_path)
    await gcs_utils.upload_gcs_object(GCS_SN_BUCKET, key, data, VOICE_ANSWER_CONTENT_TYPE)

    answer = await db.get(SnVoiceAnswer, (session_id, resource_path))
    if answer is None:
        answer = SnVoiceAnswer(session_id=session_id, resource_path=resource_path)
        db.add(answer)
    answer.storage_key = key
    answer.size = len(data)
    answer.content_type = VOICE_ANSWER_CONTENT_TYPE
    await db.commit()
    return answer
