---
status: accepted
date: 2026-09-29
---

# A warning stands apart from the status, and only the Desk attending ends it

A **Warning** used to be written as the status `needs_person` with the halt kind `warning`.
Every reader therefore saw a room that had stopped, although a warning refuses nothing, and
any landing turn lifted it with the status. That is how the hard-stretch mark vanished at the
next read (hand test of 2026-09-28, item 7.4). It also broke invariant 15 of ADR 0046 in the
internalization-room repository: a warning is the same on the tablet, on the server and on the
Desk.

Decided by Henok on 2026-09-29 (ENG-1163):

- A warning has its own column, the moment it was raised. `needs_person` means a blocking
  halt only, and raising a warning never writes the status. A session stays in progress, or
  done, while a warning stands.
- A warning stands while that column is set and nobody is marked as having attended the
  session. Only the Desk attending ends it, and undoing the attendance brings it back. Neither
  write touches the warning itself: the rule reads the attendance stamps, which the Desk
  already writes and every new halt already clears.
- One crossing raises one warning. The text seam no longer raises it a second time after the
  round's verdict, which it did only because the verdict used to lift it.
- A landing turn lifts a blocking halt, as before, and never a warning. The count a turn
  compares to tell the halt it began in from a newer one counts blocking halts only, so a
  warning raised while the Guide answers does not keep a blocking halt standing.
- Every new halt clears the attendance stamps, as before. A warning the cleared visit had
  ended stays ended: once the stamps go the visit can no longer be undone, so what it ended
  is final.
- Every read answers the standing halt the same way: the room's state, the Desk's queue row,
  the attended answer and the team card, which gains a `halt` field. A blocking halt reads
  `blocking` whether or not a warning stands under it. Once the blocking halt is lifted by a
  turn, the warning reads again.
- **One attendance ends both.** When a blocking halt stands over a warning, the facilitator
  who came is in the room for either, so one visit ends both. The ticket's "the warning reads
  again once the blocking halt is lifted" is therefore witnessed with the other lift, a
  landing turn.
- The Desk's queue lists a session under a standing warning next to the halted and the
  finished ones. The Desk's client still filters on `needs_person` until ENG-1169 changes it,
  so this change ships together with that one.

The migration carries every standing warning out of the status: a row with `needs_person`
and halt kind `warning` gets its warning moment set to the row's last update. Its status goes
back to `done` when the passage had closed, because `ended_at` is written only with `done`,
and to `in_progress` otherwise. A visit made before the deploy that had lifted a warning
(`lifted_halt` warning) becomes an attended warning: its warning moment is the visit's and
`lifted_halt` is cleared, so undoing that visit brings back a warning and never a blocking
halt. The upgrade drops a blocking halt that stood under a warning, standing or visited: the
old code had already written the warning's kind over it, so the row no longer said a blocking
halt was there, and every reader already took it for a warning. The downgrade puts
`needs_person` back on every row where a warning still stands, and `lifted_halt` warning on
every row where a visit ended one. A standing-warning row comes back with the kind of its last
halt, which is a blocking one if a blocking halt was raised and lifted over the warning after
the upgrade.

Rejected: clearing the warning column when the Desk attends and restoring it on the undo. The
record of what one visit ended is a single column (`lifted_halt`), and one visit can end two
halts. Reading the warning from the attendance stamps needs no second record of the lift.
