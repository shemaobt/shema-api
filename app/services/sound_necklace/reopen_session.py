from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import SessionLockChanged
from app.db.models.sound_necklace import AuditEvent, SessionStatus, SnSession
from app.services.sound_necklace.lock_fence import raise_if_locked_by_other
from app.services.sound_necklace.record_audit_event import record_audit_event


async def reopen_session(db: AsyncSession, session: SnSession, actor_user_id: str) -> SnSession:
    """Put a completed session back in progress. Idempotent.

    Fenced like completing it, and for the same reason: this moves the very column
    ``complete_session`` guards, so leaving it open would let the loser simply undo the
    winner's completion.
    """
    if session.status is SessionStatus.IN_PROGRESS:
        return session

    now = datetime.now(UTC)
    reopened = (
        await db.execute(
            update(SnSession)
            .where(
                SnSession.id == session.id,
                # Predicates on the target row, not the autosave's NOT EXISTS: a subquery
                # carries its own uncorrelated scan of sn_sessions and would re-run under
                # this statement's original snapshot when a concurrent acquire forces a
                # re-check, reporting a session free that has just been taken.
                SnSession.lock_expires_at.is_(None)
                | (SnSession.lock_expires_at <= now)
                | (SnSession.locked_by == actor_user_id),
            )
            .values(status=SessionStatus.IN_PROGRESS, completed_at=None)
            .returning(SnSession.id)
            .execution_options(synchronize_session=False)
        )
    ).scalar_one_or_none()

    if reopened is None:
        await raise_if_locked_by_other(db, session.id, actor_user_id)
        # Refused, but the lease lapsed before we could name the holder. Nothing landed;
        # falling through would answer 200 with a session still marked complete.
        raise SessionLockChanged("The session lock changed hands. Try reopening again.")

    await record_audit_event(
        db,
        event=AuditEvent.SESSION_REOPENED,
        user_id=actor_user_id,
        project_id=session.project_id,
        resource_ref=session.id,
        session_id=session.id,
    )
    await db.commit()
    await db.refresh(session)
    return session
