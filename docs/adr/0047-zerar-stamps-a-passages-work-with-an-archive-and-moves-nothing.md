---
status: accepted
date: 2026-10-06
---

# Zerar stamps a passage's work with an archive and moves nothing

Marcia's facilitator gives a team a clean passage with Zerar: every session of the pericope, in
every language, with the voice's replies, the kept rehearsals, the recording, the telling-back
and its history, moves under `archive/<stamp>/` in her file stores; a manifest records what went
where, with each session's dossier as it stood; nothing is deleted («zerado só para a equipe»,
2026-09-15); the raised-hand questions stay. Our room holds the same work in five tables and in
GCS objects keyed by session, and ADR 0045's open door returns the team's latest session, or
claims the latest stored one when the pointer is gone.

Decided with Henok on 2026-10-06 (ENG-1261):

- An archive is a row in `ir_archives` (project, pericope, archived at, by whom, a snapshot of
  each session as it stood) and a nullable `archive_id` on `ir_sessions`, `ir_takes`,
  `ir_segments`, `ir_coverage_events` and `ir_releases`. Zerar stamps the pericope's rows in
  every language in one transaction and deletes the `ir_team_sessions` pointer rows of that
  pericope. Nothing moves in the database or in GCS, so nothing can be lost or overwritten
  half-way.
- Every door that lists or picks work reads live rows only: the open door, the latest-stored
  fallback and the history behind it, the facilitator's session list, takes, segments,
  releases and the necklace's history of touches. The next open therefore mints a new session;
  an archived one is never returned or resurrected.
- A door that names an archived session answers as ADR 0051 answers a gone session, so the
  tablet returns to the Choice.
- `ir_questions` is never stamped: the raised hands are the field's signal, as in her reset.
- A pericope with nothing live creates no archive and says so in a field, never a 409.
- Release versions keep counting across archives: the unique index on (project, pericope,
  version) stays, so Refine never receives two files under one name. Her draft store restarts
  `finalizeCount` at one; this is a deliberate difference.
- The Panorama's `OV-<book>` is a pericope like any other to Zerar.

Rejected: copying rows into archive tables and objects into archive prefixes, then removing the
originals, as her file stores do. A copy-then-delete on GCS is not atomic, it doubles the
schema, and it turns "never remove an original whose archived copy is not in place" into a
program to get right instead of a property of the data.
