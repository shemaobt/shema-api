from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.sound_necklace import AuditEvent, SnSession, SnVoiceAnswer
from app.services.oral_collector import gcs_utils
from app.services.sound_necklace.constants import DOWNLOAD_URL_EXPIRY_MINUTES, GCS_SN_BUCKET
from app.services.sound_necklace.record_audit_event import record_audit_event


async def voice_answer_url(
    db: AsyncSession, session: SnSession, resource_path: str, actor_user_id: str
) -> str:
    """A short-lived signed GET for one voice answer.

    The bytes are never proxied — the recording is served straight from the private
    bucket. This is a listener's own voice, which is the reach §12 most wants a record of,
    so the issuance is recorded and the commit is what returns the URL.

    The path is the ref: it is the answer's own key alongside the session, and it arrives
    already validated against the closed allowlist.
    """
    answer = await db.get(SnVoiceAnswer, (session.id, resource_path))
    if answer is None:
        raise NotFoundError("No voice answer at this path")

    url = await gcs_utils.generate_signed_download_url(
        GCS_SN_BUCKET,
        answer.storage_key,
        expiry_minutes=DOWNLOAD_URL_EXPIRY_MINUTES,
    )
    await record_audit_event(
        db,
        event=AuditEvent.VOICE_URL_ISSUED,
        user_id=actor_user_id,
        project_id=session.project_id,
        resource_ref=resource_path,
        session_id=session.id,
    )
    await db.commit()
    return url
