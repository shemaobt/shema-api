from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.sound_necklace import ConsentType, SnSession, SnSessionState
from app.models.sound_necklace import SessionCreate
from app.services.project.get_project_or_404 import get_project_or_404
from app.services.sound_necklace.project_settings import stamp_resolved_bead_sec
from app.services.sound_necklace.record_consent import record_consent


async def create_session(db: AsyncSession, user: User, payload: SessionCreate) -> SnSession:
    """Open a session on a bucket audio, at the first station and with no state yet.

    The state row is created empty alongside the session so that every autosave is a
    plain conditional UPDATE — there is no insert-or-update race on the first save.

    The consent the setup screen confirms is recorded here, in the same transaction: this
    is the path the SPA actually takes, so a consent record written only by the explicit
    route would have no caller and the boolean below would go on being the only truth.
    A false records nothing at all — the table holds consents that were given, and absent
    is not the same claim as refused.
    """
    # A platform admin skips assert_project_access, so a nonexistent project_id would
    # otherwise reach the FK as a 500 instead of a 404.
    await get_project_or_404(db, payload.project_id)
    session = SnSession(
        project_id=payload.project_id,
        created_by=user.id,
        audio_ref=payload.audio_id,
        story_name=payload.story_name,
        slug=payload.story_slug,
        manifest_id=payload.manifest_id,
        granularity_level=payload.granularity_level,
        bead_sec=payload.bead_sec,
        pipeline_consent=payload.pipeline_consent,
    )
    db.add(session)
    await db.flush()
    db.add(SnSessionState(session_id=session.id))
    await stamp_resolved_bead_sec(
        db, payload.project_id, payload.granularity_level, payload.bead_sec
    )
    if payload.pipeline_consent:
        # record_consent commits — the session, its state row and the consent land
        # together in that one transaction.
        await record_consent(db, session.id, ConsentType.PIPELINE_USE, user.id)
    else:
        # No consent to record: this is the commit that stores the session and its state.
        await db.commit()
    await db.refresh(session)
    return session
