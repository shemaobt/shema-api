from datetime import UTC, datetime

from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import SessionLockChanged
from app.db.models.sound_necklace import AuditEvent, SessionStatus, SnSession, SnSessionTick
from app.services.sound_necklace.lock_fence import raise_if_locked_by_other
from app.services.sound_necklace.record_audit_event import record_audit_event


async def complete_session(db: AsyncSession, session: SnSession, actor_user_id: str) -> SnSession:
    """Mark a session complete. Idempotent: completing a completed session is a no-op.

    ``current_step`` is deliberately left alone — it records where the state was
    left, and a completed session simply displays as the last station. Reopening
    then lands back on the real one.

    Fenced in the statement, like the autosave: a tab that was paused through a
    takeover must not finish a session somebody else is now editing.

    Clearing ``last_working_tick_at`` is what freezes the net working time. Without it
    the first heartbeat after a reopen would measure from the last live beat and charge
    the whole stretch the session spent closed, which the idle rule only hides while that
    stretch happens to exceed five minutes.

    The session's heartbeat rows are deleted in the same transaction, so a session can
    never be completed with its ticks still present. While the total can still move the
    ticks earn their keep: they are what lets the number be re-derived rather than merely
    believed. Once it is frozen they sustain nothing but a stamped record of when the
    listener was at work and for how long, which is the §14 surveillance the lock
    heartbeat is kept out of the audit log to avoid — and auditability over a number that
    can no longer change does not buy enough to justify keeping one. A fifteen-second
    beat also leaves around 1,900 rows per eight-hour session, so the volume argument
    runs the same way, but privacy is the reason.
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
            .values(status=SessionStatus.COMPLETED, completed_at=now, last_working_tick_at=None)
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

    await db.execute(
        delete(SnSessionTick)
        .where(SnSessionTick.session_id == session.id)
        .execution_options(synchronize_session=False)
    )

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
