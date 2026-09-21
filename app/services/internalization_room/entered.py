"""Whether a session is a room the team entered.

The invitation door and the panorama spoke mint a session before any stored row is read,
and the stored row wins once it is (ADR 0033 of the internalization-room repository: the
minted session is left referenced by nothing). What is left behind is one row of
`ir_sessions` with empty `messages` and no take — a launch nobody entered, not a room of
the team.

**Entered** is `messages` holding at least one turn, a row of `ir_takes` carrying this
session's id, or a halt this session ever asked for. A turn is a non-empty `messages`,
never a row of `ir_turns`: that table is a resend cache, written only when the client sent
a `turn_id` (`app/api/internalization_room/sessions.py`), and is not the durable record of
a turn — `sessions._land` is (`app/services/internalization_room/sessions.py`).

**Calling a person is an act of the team, decided with Henok on 2026-09-21.** The tablet can
ask for one (`POST /sessions/{id}/needs-person`) before any turn lands — a slow-record
watchdog, or resuming a passage whose parts never came back — and the Desk attends a room
from this same column. A halt that never got a turn is not the minted, referenced-by-nothing
row ADR 0033 describes; it is a team the room already stopped for. The halt is read the way
`halt.last` reads it (`app/services/internalization_room/halt.py`): `halt_kind`, written on
every halt and cleared by none, so a room a facilitator has since attended does not drop back
out — a lifted halt is still a halt this session asked for — with `status == needs_person`
beside it for a pre-ENG-609 row that has no `halt_kind` to read.

One predicate, so the Desk's column (`team_sessions._history_of`) and the team's last
activity (`list_facilitator_teams._last_activity_subquery`) cannot drift apart on what
counts as a room. `messages` is a Postgres `json` column, not `jsonb`, so the emptiness
test is `json_array_length`, which both dialects have for that type — `jsonb_array_length`
is not. The take check reuses the join predicate `progression.finished_passages` already
keys off this same table (`IRTake.session_id == IRSession.id`), as a correlated `EXISTS`
rather than an `IN (SELECT …)`: one statement per caller, not the per-team fan-out the
house doctrine in `progression.py` and `list_facilitator_teams.py` warns about.
"""

from __future__ import annotations

from sqlalchemy import ColumnElement, func, or_, select

from app.db.models.internalization_room import IRSession, IRSessionStatus, IRTake


def entered() -> ColumnElement[bool]:
    return or_(
        func.json_array_length(IRSession.messages) > 0,
        select(IRTake.id).where(IRTake.session_id == IRSession.id).exists(),
        IRSession.halt_kind.is_not(None),
        IRSession.status == IRSessionStatus.NEEDS_PERSON,
    )


__all__ = ["entered"]
