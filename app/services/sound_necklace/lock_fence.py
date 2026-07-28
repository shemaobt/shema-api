"""The lease predicate the write statements carry, and the conflict they raise.

The check rides in the same statement that writes the content: a separate "is the lock
still mine?" call is a race with extra steps, since the lease can turn over between the
check and the write. So this module exports a SQL predicate rather than a guard function
— callers paste it into their own WHERE.

That narrows the window to the width of one statement; it does not close it. This
compiles to a subquery with its own scan of sn_sessions, which does not correlate to the
row being written, so a concurrent acquire committing mid-statement is not seen: the
subplan re-runs under the statement's original snapshot. Closing that needs the guard to
be a predicate on the target row's own columns, which only works when the target IS
sn_sessions — see complete_session. The autosave writes sn_session_state and has no such
option.

The residual window is acceptable because this is an advisory lock in Kleppmann's
efficiency sense, not a correctness one: it stops two people wasting effort on the same
session. The case it exists for — someone acquires, and a stale tab writes seconds later
— is fenced correctly, because that write's snapshot postdates the acquire. Only a write
racing an acquire inside the same instant slips through.

What is fenced: the autosave, complete, reopen, and the artifact upload. What is not:
the voice /resources routes, where ENG-264 left the guard out deliberately — tightening
that is its own issue, not a gap here. The artifact upload is a check-then-act rather
than a guarded statement, because its write goes to storage and no SQL predicate fences
an external side effect.

The holder is the JWT's user. The SPA sends no per-tab token on any lock route and none
on autosave (the autosave body is the client's own opaque document, which it re-reads
under a strict schema — a field this API added there would come back as an unresumable
session), so the user is the only identity available on the wire. The cost is that two
tabs of the *same* user do not fence each other; the threat this exists for is two
different people.
"""

from datetime import UTC, datetime

from sqlalchemy import ColumnElement, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.db.models.auth import User
from app.db.models.sound_necklace import SnSession
from app.services.sound_necklace.get_lock_status import as_utc, holder_name


class SessionLockedByOther(ConflictError):
    """A write from someone who is not the current holder.

    Carries who holds it and until when; the router turns it into the 409 body, since
    the global ConflictError handler emits only {detail, code} and would drop both.
    """

    def __init__(self, holder_name: str, expires_at: datetime) -> None:
        super().__init__(f"This session is being edited by {holder_name}.")
        self.holder_name = holder_name
        self.expires_at = expires_at


def not_locked_by_other(session_id: str, user_id: str, now: datetime) -> ColumnElement[bool]:
    """True while no live lease belongs to somebody else. Permissive by default.

    An unlocked session passes: the real SPA autosaves without ever acquiring a lock,
    and a guard that demanded one would turn every one of its saves into a conflict.
    """
    return ~(
        select(SnSession.id)
        .where(
            SnSession.id == session_id,
            SnSession.lock_expires_at > now,
            SnSession.locked_by != user_id,
        )
        .exists()
    )


async def raise_if_locked_by_other(db: AsyncSession, session_id: str, user_id: str) -> None:
    """Diagnose a write that matched no rows, naming the holder if the lease is why.

    Only ever called once a guarded write already failed, so the extra read costs
    nothing on the path that succeeds.
    """
    now = datetime.now(UTC)
    row = (
        await db.execute(
            select(SnSession.lock_expires_at, User.display_name, User.email)
            .join(User, User.id == SnSession.locked_by)
            .where(
                SnSession.id == session_id,
                SnSession.lock_expires_at > now,
                SnSession.locked_by != user_id,
            )
        )
    ).first()
    if row is not None:
        expires_at, display_name, email = row
        raise SessionLockedByOther(holder_name(display_name, email), as_utc(expires_at))
