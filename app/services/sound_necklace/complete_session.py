from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import SessionLockChanged
from app.db.models.sound_necklace import AuditEvent, SessionStatus, SnSession
from app.services.sound_necklace.lock_fence import raise_if_locked_by_other
from app.services.sound_necklace.record_audit_event import record_audit_event


async def complete_session(db: AsyncSession, session: SnSession, actor_user_id: str) -> SnSession:
    """Mark a session complete. Idempotent: completing a completed session is a no-op.

    ``current_step`` is deliberately left alone — it records where the state was
    left, and a completed session simply displays as the last station. Reopening
    then lands back on the real one.

    Fenced in the statement, like the autosave: a tab that was paused through a
    takeover must not finish a session somebody else is now editing.
    """
    if session.status is SessionStatus.COMPLETED:
        return session

    now = datetime.now(UTC)
    completed = (
        await db.execute(
            update(SnSession)
            .where(
                SnSession.id == session.id,
                # Spelled against the target row's own columns rather than reusing the
                # autosave's NOT EXISTS. A subquery carries its own scan of sn_sessions,
                # which does not correlate to the row being updated — so when a concurrent
                # acquire forces a re-check, the subplan re-runs under this statement's
                # original snapshot and still reports the session free. Column predicates
                # on the target are re-evaluated against the updated tuple, which is the
                # exclusion this needs. The autosave writes a different table and has no
                # such option.
                SnSession.lock_expires_at.is_(None)
                | (SnSession.lock_expires_at <= now)
                | (SnSession.locked_by == actor_user_id),
            )
            .values(status=SessionStatus.COMPLETED, completed_at=now)
            .returning(SnSession.id)
            .execution_options(synchronize_session=False)
        )
    ).scalar_one_or_none()

    if completed is None:
        # The lease is the only guard on this write, so it is the only thing that can
        # have refused it. Nothing matched, so nothing is pending to roll back.
        await raise_if_locked_by_other(db, session.id, actor_user_id)
        # Refused, yet by the time we looked the lease had lapsed and there is no holder
        # left to name. Falling through would commit nothing and answer 200 with an
        # uncompleted session — a no-op reported as success. Say what happened instead;
        # the client's next attempt finds the session free.
        raise SessionLockChanged("The session lock changed hands. Try completing again.")

    await record_audit_event(
        db,
        event=AuditEvent.SESSION_COMPLETED,
        user_id=actor_user_id,
        project_id=session.project_id,
        resource_ref=session.id,
        session_id=session.id,
    )
    await db.commit()
    await db.refresh(session)
    return session
