---
status: accepted
date: 2026-10-23
---

# A visit names the halt it answers: the halt count and the warning

A **Visit** and its undo were written blind. The Desk reads the queue every 15 s, and a tap
lands seconds after the read. A visit read under one halt that landed after the next one
stamped the newer halt and hid it from the queue. A stale undo cleared a colleague's later
visit. ADR 0076 made the visit a record; this decides which halt the record answers.

Decided by the ticket's rule (ENG-1761), Henok's decision of 2026-10-22 and the Definer's
answer of 2026-10-23:

- A halt is named by two values: the room's **Halt count** (`halts_raised`), which only a
  blocking halt moves (ADR 0039 is unchanged), and its warning moment (`warned_at`), which
  only a warning moves. The Desk's two reads, the queue and «Sessões», serve both.
- `POST` and `DELETE …/facilitator/sessions/{id}/attended` take the two as query parameters:
  `halt`, required, and `warning`, an instant with its offset, absent when the Desk saw no
  warning. A missing or invalid `halt`, or a `warning` with no offset, is the framework's own
  422. No blind write survives.
- The write is one guarded statement, `WHERE halts_raised = :halt AND warned_at IS NOT
  DISTINCT FROM :warning`. A visit also requires no stamp, so a second tap writes nothing and
  keeps the first stamp. An undo also requires a stamp. A write that changed nothing while
  either value moved answers 409 `HALT_MOVED` with the current `halts_raised` and `warned_at`,
  and the Desk reads again and draws the newer halt, with no toast.
- The queue serves the standing warning's moment, which is the room's own on every row the
  Desk can visit: an unattended one. «Sessões» serves the room's own, which is what an undo
  names.
- The role gate answers first, and a room of another team answers 404 whatever count it
  names, so a count never leaks across teams. A refused write nudges nothing.
- On a demo team the undo decides whether a halt still stands in the same statement that
  clears the stamps (ADR 0064). A halt raised or lifted after the undo read the room is the
  one it answers.
- The server's own visit to a demo team's halt names the halt it has just raised.
- The tablet's own halt (`/facilitator/devices/{id}/attended`) is not changed.

Consequences:

- An old Desk gets 422 on every visit and undo until the new one is deployed, and shows its
  refusal sentence. Nothing is written. The API deploys first.
- A room on the queue's Refine half with a visit to its warning reads no warning on the
  queue. The Desk never visits from that half; an undo of it names what «Sessões» serves.

Rejected:

- A guard inside the request on the API alone (Henok, 2026-10-22). It leaves the poll window
  open.
- The count in a body on the DELETE. Proxies and clients treat it unevenly, and a query reads
  the same on both verbs.
- A warning moving the halt count. It would reverse ADR 0039: a warning raised while the
  Guide answers would keep the blocking halt standing until the team's next return.
- A new counter column for warnings. It is a migration, for a fact `warned_at` already holds.
