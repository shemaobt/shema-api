---
status: accepted
date: 2026-09-08
---

# A **Correction** is a new row for the same position, never an edit in place

A **Stretch** is versioned by writing another row for the position it holds, not by editing
the row that is already there. `superseded_at` is what stops the counting, and
`superseded_by_id` is what took its place.

The second column is null when the stretch was **Abandoned** rather than replaced, which is
what starting a telling-back over does to every stretch of a session at once. Two facts, and
the second one does not always exist, so one column could not carry both.

The rejected alternative was the edit: one row per position, updated in place, with the
history kept somewhere else or not at all. It fails the thing the room is for. A **Superseded**
attempt and its findings become marked history and never vanish, which is what lets a
facilitator see what a team actually did, and what lets **Pass** and **Retell** be counted at
all.
