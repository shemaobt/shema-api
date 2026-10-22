---
status: accepted
date: 2026-10-21
---

# The Desk's visit is a record, and only the team's return lifts `needs_person`

The Desk's «atendido» wrote `in_progress` over a blocking halt, so a tablet that read the
session went on because somebody tapped a row on a screen in another room. ENG-1354 makes the
team's tap on the person sign the tablet's only way out of a halt, and the server stops moving
the session for the Desk.

Decided with the Definer on 2026-10-21 (ENG-1354). Amends ADR 0039, 0044, 0045 and 0064.

- A visit stamps `attended_at` (the first one wins) and `attended_by`, and writes nothing on
  the status. Undoing it clears the stamps and writes nothing on the status either.
- `needs_person` is lifted only by the team's own return: a turn that lands, or a tablet
  opening the session. A closed passage still goes back to `done` on that return, which is now
  the only door ADR 0044's rule governs.
- The queue lists a `needs_person` room only while nobody is marked as having gone: the visit
  takes it off, the undo puts it back, and a new halt clears the stamps and lists it again.
- A demo team's halt is stamped by the server at once, so it never reaches the queue; its
  status stays `needs_person` until the team returns (ADR 0064).
- The visit still ends a warning, and undoing it brings the warning back. Over a blocking
  halt it ends the warning and leaves the halt to the team (amends ADR 0039's "one visit ends
  both").
- `lifted_halt` is read and written by nothing. The column stays.

Considered: keeping an attended halted room on the queue until the team returns. Rejected,
because the mark would then drain nothing and a facilitator could not tell a room somebody went
to from one nobody did. Also considered: dropping `lifted_halt` here. Left to its own ticket,
because it needs a migration.

Consequences: a tablet on a build that still lifts by reading the session, and whose call for a
person landed, waits for its own return (a turn that lands, or reopening the session); every
pilot tablet takes the store build that clears the sign by a tap. The Desk's undo has to be
reachable from the queue, because an attended halted room keeps the `needs_person` state the
session tile gated its undo on.
