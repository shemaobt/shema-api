---
status: accepted
date: 2026-09-25
---

# An addition or an unclear with no readable frase is dropped, not raised without one

Every finding is a statement about a **Chunk**. A **Missing with an address** and a **Missing
without an address** are both meaningful — the story simply has not been told that far, and
`_landed_without_a_frase` already counted that case. An addition or an unclear naming no chunk
at all, or one outside the reading the analyst was given, is different: it names nothing the
team can act on. Before this decision the parser still raised it, with `segment_id` null, and
it reached the tablet as a finding with no stretch and closed with `CLOSING_SPOKEN` — a spoken
answer about a boundary the team was never shown.

Decided: an addition or an unclear that resolves to no chunk is dropped the way the retired
evidence kind already is (ADR 0013) — a warning names the kind and the analyst's note, the raw
reply is kept behind it, and the rest of the reply is still read. It never becomes a `Finding`,
so it is in neither the verdict nor the **Retroverification file**.

Henok ruled the same day that only this — the no-stretch branch — retires. An **unclear** the
analyst still manages to land on a stretch keeps `CLOSING_SPOKEN`: `points_at_a_stretch`
already excludes `unclear` from the two-microphone screen, because the question it asks is a
boundary one and not "is this stretch right", and that is unaffected by whether the finding
names its chunk.

Rejected: keeping the fallback to a homeless finding for every kind, on the reasoning that a
model's inability to give a frase should never lose the finding outright. Rejected because a
homeless addition or unclear cannot be acted on by the team either way — there is no screen for
it that names a stretch — and the old fallback did something worse: it spoke a line asking the
team to answer, out loud, a boundary question about content they cannot locate.

No migration touches a row written before this deploy. A stored `addition` or `unclear` with
`segment_id` null keeps reading exactly as it did — the drop happens only at the reader, on a
fresh reply — and `closing_block` already answers that shape correctly, unchanged.
