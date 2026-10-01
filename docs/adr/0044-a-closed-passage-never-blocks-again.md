---
status: accepted
date: 2026-10-01
---

# A closed passage never blocks again

A needs-person ask on a session whose passage had closed wrote `needs_person` over `done`, and
the next lift (the Desk attending, or a landing turn) wrote `in_progress` with `ended_at` still
set. The row then left the release queue, and the Desk read a closed passage as a room still
going on. ADR 0039 already noted that `ended_at` is written only with `done`; the doors did not
keep it.

Decided by Henok on 2026-09-30 (ENG-1180):

- The needs-person ask on a closed passage is refused with `PASSAGE_CLOSED` and writes
  nothing, also when the passage closes while the ask is on its way. The tablet reads refusals
  by code. The status, 409, was the implementer's call: the request is well formed and the
  session's state refuses it, the way `NOTHING_TO_HEAR` is.
- Every lift of a blocking halt restores `done` when the passage is closed, and `in_progress`
  otherwise. Attending and a landing turn read the same rule.
- A warning may still stand on a closed passage (ADR 0039): it refuses nothing.
- The rows the old code left `in_progress` with `ended_at` set go back to `done` in a data
  migration whose downgrade leaves them `done`. A closed passage still carrying `needs_person`
  is left alone: a blocking halt stands on it, and the next lift closes it again.

Rejected: turning the ask on a closed passage into a warning. It is a new product rule for a
case that should not happen.
