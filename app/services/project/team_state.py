"""When the Desk calls a team stopped — decided here, once, and served.

The front end is deliberately not left to infer this from a timestamp. Two screens reading
the same date and applying their own idea of "a while" is how one number starts disagreeing
with another, and the facilitator believes whichever they saw last.
"""

from datetime import UTC, datetime, timedelta

from app.models.team import TeamState

#: How long a passage may go untouched before the team reads as stalled.
#:
#: **Derived, then confirmed — both halves matter to whoever changes it.** It was read off
#: the Desk's own fixtures, where the stalled teams sit at 18, 25 and 30 days and the oldest
#: team still called `in_progress` sits at 15, which leaves the boundary somewhere between 16
#: and 18 days; 21 is the round number inside that window. The product owner approved it on
#: 2026-08-20. So it is neither arbitrary nor a rule handed down from the field, and anyone
#: replacing it is contradicting a decision, not correcting a guess.
STALLED_AFTER = timedelta(days=21)


def _as_utc(when: datetime) -> datetime:
    """A stored moment, made comparable.

    Postgres reads a ``timestamptz`` back aware; SQLite reads the same column back naive.
    Comparing either against ``now`` without this raises, and it raises only on one of the
    two databases — which is the kind of difference that ships.
    """
    return when if when.tzinfo is not None else when.replace(tzinfo=UTC)


def team_state(
    *,
    passage_done: bool,
    last_activity_at: datetime | None,
    now: datetime,
) -> TeamState:
    """Where a team stands, from the passage it is on and when it last did anything.

    A finished passage is never stalled, however long ago it was finished: stalled means the
    work stopped, not that the team went quiet, and a team that closed a passage and moved on
    is nobody to chase.

    A team that has never met is ``IN_PROGRESS`` and not stalled. "Never started" is not
    "stopped" — a team still waiting for its first session would otherwise arrive at the top
    of a facilitator's queue with nothing to be chased about.
    """
    if passage_done:
        return TeamState.COMPLETE

    if last_activity_at is not None and _as_utc(last_activity_at) < now - STALLED_AFTER:
        return TeamState.STALLED

    return TeamState.IN_PROGRESS
