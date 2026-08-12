import asyncio

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

    The deletions are issued concurrently, as ``store_artifacts`` issues its uploads. A
    full interview runs to a few hundred questions, so a session can carry that many
    recordings besides its three artifacts, and awaiting them one at a time is that many
    serialised round trips with a facilitator watching the menu spin.
    ``asyncio.to_thread`` runs them on the loop's default executor, so the fan-out is
    bounded by that pool rather than by the number of keys. The pool is small and
    process-wide, so a very large sweep queues behind it and holds threads other callers
    share; if that shows up in practice the answer is the bucket's batch delete, not a
    semaphore over one client per object.

    Objects go before rows, as in ``delete_voice_answer``. If any deletion raises, the
    gather propagates it, the session row is never deleted, and the rows survive pointing
    at missing objects — a playback that 404s until a retry heals it. Siblings already in
    flight are not cancelled and may still land, which is the same outcome the sequential
    version had. For LGPD-sensitive audio that is the safe direction to fail; the reverse
    leaves the recordings in the bucket with nothing left to reach them.

    The child rows go by cascade, not by hand: sn_session_state, sn_session_ticks,
    sn_artifacts, sn_voice_answers and sn_consents all carry ON DELETE CASCADE from
    sn_sessions, and sn_answer_transcripts cascades transitively from sn_voice_answers.
    Deleting them here would be a second copy of the schema's own answer, and the copy
    is what drifts when a table is added. ``sn_audit_events.session_id`` is SET NULL
    rather than cascaded, so the §12 trail outlives the session it describes.
    """
    await raise_if_locked_by_other(db, session.id, actor_user_id)

    # One statement for one question. The two halves are independent, but gathering them
    # is not the way to get that: they share this session, and two db.execute calls in a
    # gather race on its single connection.
    keys = (
        (
            await db.execute(
                select(SnArtifact.storage_key)
                .where(SnArtifact.session_id == session.id)
                .union_all(
                    select(SnVoiceAnswer.storage_key).where(SnVoiceAnswer.session_id == session.id)
                )
            )
        )
        .scalars()
        .all()
    )

    await asyncio.gather(*(gcs_utils.delete_gcs_object(GCS_SN_BUCKET, key) for key in keys))

    await db.delete(session)
    await db.commit()
