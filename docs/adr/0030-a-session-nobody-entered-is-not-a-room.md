---
status: accepted
date: 2026-09-21
---

# A session nobody entered is not a room of the team

The invitation door and the panorama spoke mint a session before any stored row is read, and
the stored row wins once it is read (ADR 0033 of the internalization-room repository: the
stored row wins at every door; the minted session is left referenced by nothing). What that
leaves behind is one row of `ir_sessions`, `in_progress`, with empty `messages` and no take —
a launch nobody entered, not a conversation the team held. Two readers answered it as if it
were: the Desk's sessions column drew it, lifted
above the live conversation because an in-progress row with no end reads as the one thing the
facilitator can still act on; and the team's last activity counted its creation moment, moving
the team up a facilitator's work queue for a passage nobody opened on purpose.

Decided: the server stops showing a session nobody entered. `entered()`
(`app/services/internalization_room/entered.py`) is the one predicate — `messages` holding at
least one turn, a row of `ir_takes` naming the session, or a halt this session ever asked for —
and both readers filter by it: the Desk's column (`team_sessions._history_of`) and the sessions
leg of the team's last activity (`list_facilitator_teams._last_activity_subquery`). No route to
close, delete or sweep a session is added; the server does not answer for a session that was
never a room, rather than closing one that was. Accepted with the rule: a room just opened
appears in the Desk's column only when its first turn lands, seconds later — the delay of one
request, not of a sweep.

**Calling a person is an act of the team, and it can happen before any turn lands** —
decided with Henok on 2026-09-21, after `test_facilitator_attends_a_halt.py` measured the gap:
the tablet can ask for a person (`POST /sessions/{id}/needs-person`) as a slow-record watchdog,
or when resuming a passage whose parts never came back, and the Desk attends a halted room from
this same column. Excluding an unentered-but-halted session by the letter of the rule above
would have hidden a team that is stuck, which the rule was never meant to do — so `entered()`
gains two more branches, both read the way `halt.last` already reads this same fact
(`app/services/internalization_room/halt.py`): `halt_kind IS NOT NULL`, because `attend`
answers the halt by putting `status` back to `IN_PROGRESS` without clearing `halt_kind` — a
room a facilitator has since gone to must not drop back out of the column on that account, and
`halt_kind` is written on every halt and cleared by none for exactly this reason; and
`status == needs_person` beside it, for a pre-ENG-609 row that has no `halt_kind` to read but
may still be standing halted. The boundary this ADR draws is "no turn, no take and no halt,"
not "no turn and no take" alone.

Rejected: a new route for the tablet to say it is done with the session it opened, so the server
could close it rather than merely hide it. That is the more exact fix — closing what opened
stays closed everywhere, including a future reader this one is blind to — but it is a new session
state, a protocol change on both sides of the invitation door, and it can only ship after the
tablets carry the build that calls it. Two slices for a fact the server already has enough
information to hide. Rejected, also, leaving it as it was: the empty portrait and the queue
jump are a defect measured on the Desk today, not a cosmetic one.

A turn is `messages` holding at least one entry, never a row of `ir_turns` — that table is a
resend cache, written only when the client sent a `turn_id`, and is not the durable record of a
turn (`app/services/internalization_room/sessions.py`'s `_land` is). `messages` is a Postgres
`json` column, not `jsonb`, so the emptiness test is `json_array_length`, which both SQLite's
JSON1 and Postgres' `json` type answer — `jsonb_array_length` is not this column's function. The
take check is a correlated `EXISTS`, reusing the join predicate `progression.finished_passages`
already keys off this same table (`IRTake.session_id == IRSession.id`): one statement per
caller, not the per-team `IN (SELECT …)` fan-out the house doctrine in `progression.py` and
`list_facilitator_teams.py` warns against.
