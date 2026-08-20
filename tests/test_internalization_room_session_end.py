"""ENG-451 — what ends a session, and how long it lasted.

The rule this exercises is **a proposal**, not an agreement. Its other half is ENG-435, in
the room app, and nobody has signed off on the idle limit — so what these tests pin is the
*shape*: that the end is the team's last activity and never the moment it was noticed, that
the limit is a boundary read off one named constant, and that the three readings of the one
fact are answered together and cannot disagree. Change the number and only the two boundary
tests move.

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
    SESSION_IDLE_LIMIT,
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

    end = end_of(working, at=OPENED + timedelta(minutes=25))

    assert end.state is SessionState.IN_PROGRESS
    assert end.ended_at is None
    assert end.duration_minutes is None, "an open conversation has no length, not a zero"


# Behaviour 2 — the completion floor is an event, so it is stamped.


def test_a_session_closed_by_the_floor_reads_complete_at_the_instant_it_closed() -> None:
    closed_at = OPENED + timedelta(minutes=34)
    finished = a_session(updated_at=closed_at, ended_at=closed_at, status=IRSessionStatus.DONE)

    end = end_of(finished, at=closed_at + timedelta(days=3))

    assert end.state is SessionState.COMPLETE
    assert end.ended_at == closed_at
    assert end.duration_minutes == 34


# Behaviour 3 — the one the acceptance criterion is about.


def test_a_session_nobody_closed_ends_where_the_team_stopped_not_where_it_was_noticed() -> None:
    """Left at 15:00 and asked about at 03:00 the next morning.

    This is the whole reason the end is derived from the last activity rather than stamped
    when somebody notices: a rule that ended it at the moment of the question would report
    twelve hours of work that nobody did, and it would report a *different* twelve hours
    every time the question was asked again.
    """
    stopped = datetime(2026, 8, 20, 15, 0, tzinfo=UTC)
    started = datetime(2026, 8, 20, 14, 13, tzinfo=UTC)
    abandoned = a_session(created_at=started, updated_at=stopped)

    end = end_of(abandoned, at=datetime(2026, 8, 21, 3, 0, tzinfo=UTC))

    assert end.state is SessionState.ABANDONED
    assert end.ended_at == stopped
    assert end.duration_minutes == 47


def test_asking_twice_about_an_abandoned_session_gives_the_same_answer_twice() -> None:
    """A duration that grows while nobody is working is the defect in its visible form."""
    abandoned = a_session(updated_at=OPENED + timedelta(minutes=47))

    first = end_of(abandoned, at=OPENED + timedelta(hours=9))
    later = end_of(abandoned, at=OPENED + timedelta(days=40))

    assert first == later


# Behaviour 4 — the limit is a boundary read off one constant, not a mood.


def test_a_session_idle_for_exactly_the_limit_is_still_going() -> None:
    quiet = a_session(updated_at=OPENED)

    assert end_of(quiet, at=OPENED + SESSION_IDLE_LIMIT).state is SessionState.IN_PROGRESS


def test_a_session_idle_past_the_limit_is_over() -> None:
    quiet = a_session(updated_at=OPENED)

    end = end_of(quiet, at=OPENED + SESSION_IDLE_LIMIT + timedelta(seconds=1))

    assert end.state is SessionState.ABANDONED


def test_a_halted_session_ends_by_the_idle_rule_like_any_other() -> None:
    """`needs_person` is a halt, not an end — a turn that lands puts it back in progress."""
    halted = a_session(updated_at=OPENED, status=IRSessionStatus.NEEDS_PERSON)

    assert end_of(halted, at=OPENED + timedelta(minutes=5)).state is SessionState.IN_PROGRESS
    assert (
        end_of(halted, at=OPENED + SESSION_IDLE_LIMIT + timedelta(seconds=1)).state
        is SessionState.ABANDONED
    )


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

    asked_at = OPENED + timedelta(hours=9)

    assert end_of(naive, at=asked_at) == end_of(aware, at=asked_at)


def test_a_naive_stamped_end_is_read_as_utc() -> None:
    """The stamped half of the same trap: the end itself, not only the arithmetic."""
    closed_at = datetime(2026, 8, 20, 9, 34)
    finished = a_session(
        created_at=datetime(2026, 8, 20, 9, 0),
        updated_at=closed_at,
        ended_at=closed_at,
        status=IRSessionStatus.DONE,
    )

    end = end_of(finished, at=OPENED + timedelta(days=1))

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

    assert end_of(finished, at=closed_at).duration_minutes == minutes


# Behaviour 7 — a session in which nothing was ever said has no length, not the idle stretch.


def test_a_session_abandoned_without_a_word_lasted_no_time_at_all() -> None:
    opened_and_left = a_session(updated_at=OPENED)

    end = end_of(opened_and_left, at=OPENED + timedelta(days=1))

    assert end.state is SessionState.ABANDONED
    assert end.duration_minutes == 0, "nothing happened; the idle stretch is not the team's time"
