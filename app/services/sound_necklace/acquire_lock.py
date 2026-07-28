from datetime import UTC, datetime, timedelta

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.sound_necklace import SnSession
from app.services.sound_necklace.get_lock_status import (
    LockState,
    as_utc,
    get_lock_status,
    holder_name,
)

# Sized for a 15s client heartbeat: four times the beat tolerates three missed ones
# (a slow query, a cold start, a transient 503) before anyone else can take the
# session. The BCD lock's 4h is the wrong scale — two people editing live need
# recovery in minutes, not an afternoon.
LOCK_TTL = timedelta(seconds=60)


async def acquire_lock(db: AsyncSession, session: SnSession, user: User) -> LockState:
    """Take or renew the advisory lease; report who holds it either way.

    Acquire and renew are one statement, so the client's heartbeat is idempotent: it
    matches while the session is unheld, while the lease has lapsed, or while the caller
    already holds it.

    Losing is not an error — the returned state names the current holder, and the SPA
    opens the session in review mode off it.
    """
    now = datetime.now(UTC)
    # The guarded UPDATE is the entire mutual exclusion, and the new expiry comes back
    # from the statement itself. Reading it afterwards would answer a different question
    # than the write did: on a contended row the SELECT can hand the winner's lease to
    # the loser, which is how a loser convinces itself it won.
    expires_at = (
        await db.execute(
            update(SnSession)
            .where(
                SnSession.id == session.id,
                SnSession.locked_by.is_(None)
                | (SnSession.lock_expires_at <= now)
                | (SnSession.locked_by == user.id),
            )
            .values(locked_by=user.id, lock_expires_at=now + LOCK_TTL)
            .returning(SnSession.lock_expires_at)
            # The guard is the database's to decide. Left on auto, SQLAlchemy tries to
            # evaluate the WHERE in Python against the identity map, which is both a
            # different answer than the one the UPDATE gave and a crash on SQLite,
            # whose datetimes come back naive.
            .execution_options(synchronize_session=False)
        )
    ).scalar_one_or_none()

    if expires_at is None:
        # Matched nothing, so nothing is pending and there is nothing to roll back:
        # somebody else holds a live lease. Report them instead of raising — the
        # client has no handler for a conflict here.
        return await get_lock_status(db, session.id)

    await db.commit()
    return LockState(True, user.id, holder_name(user.display_name, user.email), as_utc(expires_at))
