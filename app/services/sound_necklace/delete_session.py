from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.sound_necklace import SnArtifact, SnSession, SnVoiceAnswer
from app.services.oral_collector import gcs_utils
from app.services.sound_necklace.constants import GCS_SN_BUCKET
from app.services.sound_necklace.lock_fence import raise_if_locked_by_other


async def delete_session(db: AsyncSession, session: SnSession, actor_user_id: str) -> None:
    """Delete a session for good — its objects, then its rows.

    The sweep is driven off the session's own rows, never off a bucket prefix. That is
    what keeps it to what this session produced: the listener's recordings and the three
    exported artifacts. The project's source audio lives in the Oral Collector's bucket
    and is reached through ``sn_audio_refs``; it belongs to the project, outlives every
    session cut from it, and is never named here. Only ``GCS_SN_BUCKET`` is.

    The lease is fenced before a single object moves. A refusal has to leave the session
    exactly as it was, and a fence that ran after the sweep would answer 409 having
    already destroyed the recordings it was refusing to touch.

    Objects go before rows, as in ``delete_voice_answer``. If the commit then fails, the
    rows survive pointing at missing objects — a playback that 404s until a retry heals
    it. For LGPD-sensitive audio that is the safe direction to fail; the reverse leaves
    the recordings in the bucket with nothing left to reach them.

    The child rows go by cascade, not by hand: sn_session_state, sn_session_ticks,
    sn_artifacts, sn_voice_answers and sn_consents all carry ON DELETE CASCADE from
    sn_sessions, and sn_answer_transcripts cascades transitively from sn_voice_answers.
    Deleting them here would be a second copy of the schema's own answer, and the copy
    is what drifts when a table is added. ``sn_audit_events.session_id`` is SET NULL
    rather than cascaded, so the §12 trail outlives the session it describes.
    """
    await raise_if_locked_by_other(db, session.id, actor_user_id)

    keys = list(
        (
            await db.execute(
                select(SnArtifact.storage_key).where(SnArtifact.session_id == session.id)
            )
        ).scalars()
    ) + list(
        (
            await db.execute(
                select(SnVoiceAnswer.storage_key).where(SnVoiceAnswer.session_id == session.id)
            )
        ).scalars()
    )

    for key in keys:
        await gcs_utils.delete_gcs_object(GCS_SN_BUCKET, key)

    await db.delete(session)
    await db.commit()
