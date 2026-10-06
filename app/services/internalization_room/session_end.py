"""When a conversation's floor was met, how long that took, and which of two it reads.

**Nothing ends a session on its own.** A session is over only because the team met the
completion floor, and that is an event at an instant, so the instant is stamped on the row:
``ended_at`` means "the floor was met at", written once by ``sessions.apply_coverage`` when
the status becomes ``done``. A session without it is in progress however long it sat, and
has no end and no length. The room app joins the same session after any silence, so a limit
of idle hours that called it over would contradict what the tablet is handed.

``needs_person`` is a halt and not an end. A turn that lands puts it back in progress
(``sessions.append_exchange``).

**Length is wall time**, and there is no working time to have: ``messages`` carries no
per-turn timestamp, so the data to sum working intervals does not exist. The honest cost is
that a break taken *inside* a session inflates it — two hours of work around a two-hour
lunch reads four. Per-turn timestamps are what would fix that, and nothing asks for them.

The three readings are answered together, out of one function, because they are one fact:
an end, a state and a length that could be computed apart are three things to keep in step.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.core.enums import SessionState
from app.db.models.internalization_room import IRSession
from app.utils.stored_time import as_utc

_SECONDS_A_MINUTE = 60


@dataclass(frozen=True)
class SessionEnd:
    ended_at: datetime | None
    state: SessionState
    duration_minutes: int | None


def end_of(session: IRSession) -> SessionEnd:
    """The one place a session's end, state and length are decided."""
    if session.ended_at is not None:
        return _over(session, as_utc(session.ended_at), SessionState.COMPLETE)
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
    "SessionEnd",
    "SessionState",
    "as_utc",
    "end_of",
]
