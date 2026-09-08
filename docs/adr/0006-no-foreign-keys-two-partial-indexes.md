---
status: accepted
date: 2026-09-08
---

# No foreign keys on the room tables, and two partial unique indexes rather than one

The room tables carry ids across an app boundary and have never constrained them. One table
with a different rule is how the next person loses an afternoon, so the stretch table matches
the **Take**, question and **Coverage event** tables and declares no foreign keys either.

Uniqueness of position is enforced by two partial unique indexes, and the second is not
redundant. A unique index treats nulls as distinct, so the one naming `parent_id` enforces
nothing at all for a stretch nobody divided, which is most of them. The second index covers
exactly that case: a **Divided stretch** is unique among its own siblings, and an undivided one
is unique among the session's undivided stretches. Both are partial on the superseded column,
so a **Superseded** row never collides with the row that replaced it.

This was measured on the migration's own database rather than assumed.
