---
status: accepted
date: 2026-10-22
---

# No door holds the session row across the bucket, and a sentence whose part moved is refused

The sentence door (ADR 0069) took the session's row `FOR UPDATE` and kept it across both uploads
to the bucket and the measure of the spliced part. ENG-1688 (#872) had already moved the splice
out of the lock, and re-spliced, without bound, whenever the part had moved by the time the lock
came back. Every transaction bounds a lock wait at 30 s (ADR 0079). The **Turn claim** and every
write of the session are an `UPDATE` of that row, so a **Team turn** or a «terminei» behind a slow
upload waited on it, and past the bound got `LockNotAvailable`, a 500, and the sign (ENG-1754).

Decided by the Definer on 2026-10-22 (recorded on the ticket):

- No door holds the session row lock across network or disk work. The sentence door reads and
  checks with nothing held and commits, then splices, uploads both recordings and measures the
  spliced part, all unlocked.
- The lock is taken only to write what they produced. Under it the session and its stretches are
  read again and the checks run again, in the order they run before the splice: the same
  sentence already laid in is answered as it stands; an id reused with another recording is
  refused; a frase that no longer counts takes no sentence; a part not in WAV is refused;
  another frase awaiting its translation is refused. Last, if the frase's part or its span is no
  longer the one spliced, the sentence is refused `PART_CHANGED` (409) and nothing is written.
  A span that moved on the same take counts as changed: the splice was made at the old span.
- The tablet treats `PART_CHANGED` as a refused step: it keeps the sentence and offers to send it
  again, and the resend is spliced into the part as it now stands. No app change.
- The uploads of a refused sentence stay in the bucket and are never deleted. Their keys are
  content-addressed, so a resend of the same recording, or a rival laying in the same bytes, can
  hold the very key just written. No sweep of the room's objects exists, and none is added.
- The session's row is taken `FOR UPDATE` in one place, the sentence door's write; a test
  witnesses it.
- ADR 0079's premise for its 30 s `lock_timeout`, a frase that holds the session's row through
  two uploads to the bucket, no longer holds. The 30 s bound is kept: the turn claim's lifetime
  is out of this ticket's scope.

This retires ENG-1688's re-splice. The two tests that pinned it now expect the refusal: the one
whose rival lays a sentence into the same part during the splice, and the one whose nuance stays
named through that race, which now sends the refused sentence again.

Rejected:

- Re-splicing until the part holds still, as #872 did: unbounded, and with the uploads unlocked
  each lap would upload both recordings again.
- Deleting the uploads on a refusal: a content-addressed key can be live under a resend.
- An advisory lock or a lock table: still a lock across the bucket.
- Locking the stretch rows instead of the session: the write rewrites the telling-back state on
  the session's row too.

Consequences: a sentence that loses the race costs the team one «tentar de novo». Objects of
refused sentences stay in the bucket, unreferenced and never served, until a sweep exists.
