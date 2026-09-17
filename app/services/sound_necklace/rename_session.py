from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import SessionLockChanged
from app.db.models.sound_necklace import SnSession
from app.services.sound_necklace.lock_fence import raise_if_locked_by_other


async def rename_session(
    db: AsyncSession, session: SnSession, story_name: str, actor_user_id: str
) -> SnSession:
    """Change a session's display name. The slug is never touched.

    That omission is the point of the function. ``slug`` names all three artifact files
    (PRD §10.5) and the downstream pipeline reads them by name, so writing it here would
    turn a label edit into a migration of objects already in the bucket — silently, and
    long after the rename looked like it had succeeded. Renaming to the same name is an
    ordinary write, not a special case.

    Fenced in the statement, like ``complete_session``, and spelled against the target
    row's own columns for the same reason: a subquery gets its own scan of sn_sessions
    that does not correlate to the row being updated, so a concurrent acquire is not
    seen. A tab paused through a takeover must not rename a session somebody else is now
    editing.
    """
    now = datetime.now(UTC)
    renamed = (
        await db.execute(
            update(SnSession)
            .where(
                SnSession.id == session.id,
                SnSession.lock_expires_at.is_(None)
                | (SnSession.lock_expires_at <= now)
                | (SnSession.locked_by == actor_user_id),
            )
            .values(story_name=story_name)
            .returning(SnSession.id)
            .execution_options(synchronize_session=False)
        )
    ).scalar_one_or_none()

    if renamed is None:
        # The lease is the only guard on this write, so it is the only thing that can
        # have refused it. Nothing matched, so nothing is pending to roll back.
        await raise_if_locked_by_other(db, session.id, actor_user_id)
        # Refused, yet by the time we looked the lease had lapsed and there is no holder
        # left to name. Falling through would commit nothing and answer 200 with the old
        # name — a no-op reported as success.
        raise SessionLockChanged("The session lock changed hands. Try renaming again.")

    await db.commit()
    await db.refresh(session)
    return session
