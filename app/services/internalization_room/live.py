"""Whether a row of a team's work is live, which is to say no Zerar has archived it.

A Zerar stamps a pericope's sessions and the rows hanging off them with an **Archive**, and
the doors that pick or list a team's work across sessions read live rows only, while the
facilitator's by-id doors still read a stamped one for the consultant (ADRs 0047 and 0052).

One predicate, so the open door, the pickers and the listings cannot drift apart on what an
archived row is, the way `entered` keeps the Desk's column and the team's last activity in
step. A row written after its session's Zerar is not stamped, so a reader that must leave it
out asks its session, not the row.
"""

from __future__ import annotations

from sqlalchemy import ColumnElement

from app.db.models.internalization_room import (
    IRCoverageEvent,
    IRRelease,
    IRSegment,
    IRSession,
    IRTake,
)

Stamped = type[IRSession] | type[IRTake] | type[IRSegment] | type[IRCoverageEvent] | type[IRRelease]


def live(table: Stamped = IRSession) -> ColumnElement[bool]:
    return table.archive_id.is_(None)


__all__ = ["live"]
