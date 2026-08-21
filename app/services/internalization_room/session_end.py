"""When a conversation ended, how long it lasted, and which of the three it is.

**The rule here is a proposal, not an agreement.** Its other half is the room app's
session-resume work (ENG-435), which says the server is the authority on session state and
leaves the staleness limit "agreed with the backend". This is the backend's half, written
down so there is one definition to agree to; nobody has agreed to the number yet.

A session ends in exactly one of two ways, and in both ``ended_at`` is the moment of the
team's **last activity** — never the moment the end was noticed.

*Completed.* The completion floor is met and the session closes. That is an event at an
instant, so the instant is stamped on the row.

*Abandoned.* Nothing has happened for longer than ``SESSION_IDLE_LIMIT``. Nothing happened,
so nothing is stamped: the end is derived here, from the last activity.

Deriving the second rather than sweeping and writing it is the decision worth defending.
The limit is not agreed, and a number nobody has agreed must not be frozen into rows — the
day the two sides settle on another one it changes here and every past session re-answers
correctly, where a written close would need a backfill to undo. It also makes an absurd
length impossible by construction rather than by a guard: a session left at 15:00 and first
asked about at 03:00 reports up to 15:00, and reports the same thing however long nobody
asks. A rule that ended it when somebody noticed would have to subtract the idle stretch
back out, and would get it wrong the day the sweep ran late.

``needs_person`` is a halt and not an end. A turn that lands puts it back in progress
(``sessions.append_exchange``), so it ends by the idle rule like any other open session.

**Length is wall time**, and there is no working time to have: ``messages`` carries no
per-turn timestamp, so the data to sum working intervals does not exist. The honest cost is
that a break taken *inside* a session inflates it — two hours of work around a two-hour
lunch reads four. Per-turn timestamps are what would fix that, and nothing asks for them.

The three readings are answered together, out of one function, because they are one fact:
an end, a state and a length that could be computed apart are three things to keep in step.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.core.enums import SessionState
from app.db.models.internalization_room import IRSession
from app.utils.stored_time import as_utc

#: How long a session may sit with nothing happening before it is over. **Proposed, not
#: agreed** — the room app holds the other half (ENG-435), and this is deliberately one
#: named constant so settling on another number is a line rather than a redesign.
#:
#: Six hours is longer than any break inside a working day: ENG-435 names the tablet put
#: down for lunch, and a two-hour lunch splitting one conversation into two is the very
#: fragmentation that issue exists to remove. And it is shorter than the gap to the next
#: morning: a session that survived the night would report a length that spans it.
SESSION_IDLE_LIMIT = timedelta(hours=6)

_SECONDS_A_MINUTE = 60


@dataclass(frozen=True)
class SessionEnd:
    ended_at: datetime | None
    state: SessionState
    duration_minutes: int | None


def last_activity(session: IRSession) -> datetime:
    """When the team last did anything to this session.

    ``updated_at`` and not a column of its own: every path that advances a session commits a
    write to that row — a turn, a classifier settle, a back-translation save, a halt. It is
    a proxy, and it is recorded as one: nothing today writes to a session row that is not
    the team's own work, and the day something does, this is the sentence that stops being
    true.
    """
    return as_utc(session.updated_at)


def end_of(session: IRSession, *, at: datetime) -> SessionEnd:
    """The one place a session's end, state and length are decided.

    ``at`` is the caller's clock rather than this module's, so the rule is a pure function
    of two timestamps and a test needs no clock to patch.
    """
    if session.ended_at is not None:
        return _over(session, as_utc(session.ended_at), SessionState.COMPLETE)

    stopped = last_activity(session)
    if as_utc(at) - stopped > SESSION_IDLE_LIMIT:
        return _over(session, stopped, SessionState.ABANDONED)

    return SessionEnd(ended_at=None, state=SessionState.IN_PROGRESS, duration_minutes=None)


def _over(session: IRSession, ended_at: datetime, state: SessionState) -> SessionEnd:
    return SessionEnd(
        ended_at=ended_at,
        state=state,
        duration_minutes=_minutes(as_utc(session.created_at), ended_at),
    )


def _minutes(started_at: datetime, ended_at: datetime) -> int:
    """Whole minutes, rounded half **up** — which is not what ``round`` does.

    The Desk computes this today with ``Math.round``, which is half-up; Python's ``round``
    is half-to-even, so thirty seconds would come back 0 where the browser said 1 and two
    and a half minutes would come back 2 where it said 3. That difference reaches the screen
    on the day the Desk deletes its copy of the arithmetic, with nothing broken and nothing
    red anywhere.
    """
    seconds = (ended_at - started_at).total_seconds()
    return int((seconds + _SECONDS_A_MINUTE / 2) // _SECONDS_A_MINUTE)


__all__ = [
    "SESSION_IDLE_LIMIT",
    "SessionEnd",
    "SessionState",
    "as_utc",
    "end_of",
    "last_activity",
]
