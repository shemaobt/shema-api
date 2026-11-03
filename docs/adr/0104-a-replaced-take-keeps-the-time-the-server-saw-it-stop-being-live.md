---
status: accepted; supersedes the `superseded_at` line of ADR 0073
date: 2026-10-29
---

# A replaced take keeps the time the server saw it stop being live

ENG-1256. The «substituída às» time of a replaced take was guessed from the arrival of the take
that replaced it, and a grain switch showed its own stamp instead. ADR 0101 left `supersededAt`
absent from the retroverificação file until a stamp existed.

Decided: `ir_takes.superseded_at` is written by the server when a rehearsal take stops being live:
a take recorded again under its number, a whole giving way to a scene part, a sentence laid into
its part, a grain switch setting it aside, or a take arriving that is no part. A take stamped keeps
its first time, so a grain switch over a take already replaced does not move it. A take stored
before the column existed has none: the take downloads and the file's `supersededAt` read the
stamp alone, and the file leaves the key out when there is none.

Rejected: backfilling the old takes from the arrival of their successors, which is the guess this
replaces and would pass it off as a record.

Consequence: a whole set aside by a grain switch now reads the switch's time as the moment it
stopped being live, not the arrival of the whole recorded after the switch back.
