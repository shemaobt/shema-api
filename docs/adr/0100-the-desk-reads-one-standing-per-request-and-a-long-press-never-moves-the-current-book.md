---
status: accepted
date: 2026-10-27
---

# The Desk reads one standing per request, and a long press never moves the Current book

Decided for ENG-1781, findings 12 and 19 of the ENG-1709 round. The Desk drew the active
passage from the team detail and the list from `/pericopes`, two requests each working out where
the team stands, so a session entered between them left no listed passage current. And
`person_arrived`, the tablet's long press, saved the room through the ORM, which moved
`updated_at`, the very column that orders a team's rooms and names its Current book.

Decided:

- The team detail carries `pericopes`, the answer of `GET /{team_id}/pericopes`, worked out from
  the one reading of where the team stands that serves `active_passage`. `/pericopes` stays
  until the Desk stops calling it.
- `person_arrived` writes `person_arrived_at` with an update that holds `updated_at` where it
  was, as ADR 0094 already asks of every write that is not the team's.

Consequences:

- The detail costs one statement more, the open findings.
- The race closes for the Desk only once its page reads `pericopes` from the detail.
