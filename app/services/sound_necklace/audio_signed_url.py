from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.sound_necklace import AuditEvent
from app.services.oral_collector import acousteme_service
from app.services.sound_necklace.record_audit_event import record_audit_event


async def audio_signed_url(
    db: AsyncSession, audio_id: str, *, project_id: str, actor_user_id: str
) -> str:
    """A short-lived signed GET for the audio's own private object.

    The bytes are never proxied through the API. The acousteme service already resolves
    the artifact and signs its private bucket/object with the ambient service account —
    the audio is in a private bucket already, so there is nothing to copy anywhere and
    this is that call.

    What this adds is the caller: the route has passed the project gate before reaching
    here, which is the entire reason the SPA is not pointed at the Oral Collector's own
    acousteme routes, which have no project scoping.

    Reaching a recorded voice is auditable (§12), so the issuance is recorded and the
    commit is what hands the URL over: a record that cannot be written becomes the
    caller's error rather than an unlogged URL. ``project_id`` and ``actor_user_id`` come
    from the route — an audio has no session to carry them, and the log must be queryable
    per project.
    """
    audio = await acousteme_service.get_audio_url(db, audio_id)

    await record_audit_event(
        db,
        event=AuditEvent.AUDIO_URL_ISSUED,
        user_id=actor_user_id,
        project_id=project_id,
        resource_ref=audio_id,
    )
    await db.commit()
    return audio.download_url
