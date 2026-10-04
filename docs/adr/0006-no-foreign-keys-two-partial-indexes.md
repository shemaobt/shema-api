---
status: accepted
date: 2026-09-08
---

# No foreign keys on the room tables, and two partial unique indexes rather than one

The stretch table declares no foreign keys, matching the **Take**, question and
**Coverage event** tables beside it.

The alternative was to declare them on this one table, since it is the newest and the most
relational of the four. It was rejected on two counts. These tables hold ids minted on the
other side of an app boundary, and a foreign key turns each arriving id into an ordering
requirement — the referenced row has to be there first — which is a promise the thing sending
them does not make. And it would have made one of the room's sibling tables behave differently from
the others, which is how the next person loses an afternoon. (Four tables when this was
written; the **Release** and hard-stretch tables joined them on 2026-09-10 under the same rule.)

The consequence is accepted rather than hidden: nothing at the database level stops a stretch
pointing at a take that is not there. What the room gets in exchange is that a row can always
be written when it arrives, in the order it arrives.

Uniqueness of position is enforced instead by two partial unique indexes, and the second is not
redundant. A unique index treats nulls as distinct, so the one naming `parent_id` enforces
nothing at all for a stretch nobody divided, which is most of them. The second index covers
exactly that case: a **Divided stretch** is unique among its own siblings, and an undivided one
is unique among the session's undivided stretches. Both are partial on the superseded column,
so a **Superseded** row never collides with the row that replaced it.

That the first index alone leaves the common case unguarded was measured on the migration's own
database rather than assumed.
