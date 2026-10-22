"""ENG-451, ENG-1263 — when a session ended, and how long it lasted.

Nothing ends a session for being idle. ``ended_at`` is the moment the completion floor was
met, written once; a session without it is in progress however long it sat, and has no end
and no length.

Two of these are here because the arithmetic is the part that reaches the screen wrong
without anything going red.

``DateTime(timezone=True)`` hands back a naive value on SQLite and an aware one on Postgres
— ``claim_code.has_expired`` says so on the same schema — and subtracting one from the other
raises. A stored naive value is read as **UTC**, never as local: a server that answered
``20:00:56`` bare was measured on the device route this week, and on a UTC-3 machine that is
three hours of error.

And the minute is rounded the way the Desk rounds it today. ``readSessionMinutes`` is
``Math.round``, which is half-*up*; Python's ``round`` is half-to-even, so 30 seconds would
come back 0 where the browser said 1. That difference reaches the screen on the day the Desk
deletes its copy of the arithmetic — with nothing broken and no test red anywhere.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.db.models.internalization_room import IRSession, IRSessionStatus
from app.services.internalization_room.session_end import (
    SessionState,
    end_of,
)

OPENED = datetime(2026, 8, 20, 9, 0, tzinfo=UTC)


def a_session(
    *,
    created_at: datetime = OPENED,
    updated_at: datetime | None = None,
    ended_at: datetime | None = None,
    status: IRSessionStatus = IRSessionStatus.IN_PROGRESS,
) -> IRSession:
    return IRSession(
        id="s",
        pericope="P01",
        status=status,
        messages=[],
        coverage_state={},
        created_at=created_at,
        updated_at=updated_at if updated_at is not None else created_at,
        ended_at=ended_at,
    )


# Behaviour 1 — a conversation still going has no end and no length.


def test_a_session_still_going_is_in_progress_with_nothing_to_measure() -> None:
    working = a_session(updated_at=OPENED + timedelta(minutes=20))

    end = end_of(working)

    assert end.state is SessionState.IN_PROGRESS
    assert end.ended_at is None
    assert end.duration_minutes is None, "an open conversation has no length, not a zero"


# Behaviour 2 — the completion floor is an event, so it is stamped.


def test_a_session_closed_by_the_floor_reads_complete_at_the_instant_it_closed() -> None:
    closed_at = OPENED + timedelta(minutes=34)
    finished = a_session(updated_at=closed_at, ended_at=closed_at, status=IRSessionStatus.DONE)

    end = end_of(finished)

    assert end.state is SessionState.COMPLETE
    assert end.ended_at == closed_at
    assert end.duration_minutes == 34


# Behaviour 3 — nothing ends a session for being idle.


def test_a_session_left_for_a_month_is_still_going_with_nothing_to_measure() -> None:
    quiet = a_session(updated_at=OPENED)

    end = end_of(quiet)

    assert end.state is SessionState.IN_PROGRESS
    assert end.ended_at is None
    assert end.duration_minutes is None


def test_a_halted_session_is_in_progress_like_any_other_open_one() -> None:
    """`needs_person` is a halt, not an end."""
    halted = a_session(updated_at=OPENED, status=IRSessionStatus.NEEDS_PERSON)

    assert end_of(halted).state is SessionState.IN_PROGRESS


# Behaviour 5 — a stored naive timestamp is read as UTC, never as local.


def test_a_naive_row_answers_exactly_what_the_aware_row_answers() -> None:
    """SQLite hands these back naive and Postgres aware, off one schema and one writer.

    Asserting the two answers are equal is stricter than asserting the naive one does not
    raise: a reading that took the naive value as local time would not raise either, and on
    a UTC-3 machine it would be three hours out.
    """
    naive = a_session(
        created_at=datetime(2026, 8, 20, 9, 0),
        updated_at=datetime(2026, 8, 20, 9, 47),
    )
    aware = a_session(updated_at=OPENED + timedelta(minutes=47))

    assert end_of(naive) == end_of(aware)


def test_a_naive_stamped_end_is_read_as_utc() -> None:
    """The stamped half of the same trap: the end itself, not only the arithmetic."""
    closed_at = datetime(2026, 8, 20, 9, 34)
    finished = a_session(
        created_at=datetime(2026, 8, 20, 9, 0),
        updated_at=closed_at,
        ended_at=closed_at,
        status=IRSessionStatus.DONE,
    )

    end = end_of(finished)

    assert end.ended_at == datetime(2026, 8, 20, 9, 34, tzinfo=UTC)
    assert end.duration_minutes == 34


# Behaviour 6 — the minute is rounded the way the Desk rounds it.


@pytest.mark.parametrize(
    ("seconds", "minutes"),
    [
        (0, 0),
        (29, 0),
        (30, 1),
        (89, 1),
        (90, 2),
        (150, 3),
        (2040, 34),
    ],
)
def test_the_length_is_whole_minutes_rounded_half_up(seconds: int, minutes: int) -> None:
    """30 and 150 are the two that tell the roundings apart.

    `Math.round` is half-up: 0.5 → 1, 2.5 → 3. Python's `round` is half-to-even: 0 and 2.
    Every other row here agrees under either rule and is there so a change of rounding is
    read as a change of rounding rather than as one odd case.
    """
    closed_at = OPENED + timedelta(seconds=seconds)
    finished = a_session(updated_at=closed_at, ended_at=closed_at, status=IRSessionStatus.DONE)

    assert end_of(finished).duration_minutes == minutes
