---
status: accepted
date: 2026-09-15
---

# A stretch is read in the order of its part, then its milliseconds

Until now the reading order of a session's stretches was the stretch `ordinal`, numbered one
past the last current sibling, which held because the only way to retire stretches was to
retire all of them at once (a telling-back started over). ENG-864 retires only the stretches of
a **Part** recorded again, and a stretch told afterwards for that part would take the next
ordinal and land at the end of the reading, after parts that come later in the passage.

Decided: the reading order is the part's number (the rehearsal take's `ordinal`, the
`parte-N` scope the tablet sends), then the stretch's `starts_ms` within that part, then the
divide hierarchy; the stretch `ordinal` keeps ordering siblings for the unique indexes of
ADR 0006 and stops ordering the passage. A **Frase number** frozen on a **Version** is
unaffected: it is frozen, not recomputed.

Rejected: renumbering the other parts' ordinals on every re-recording (rewrites rows that did
not change and races with concurrent captures). Consequence: a stretch's place in the reading
follows from where its audio sits, as ADR 0005 already says of its address.
