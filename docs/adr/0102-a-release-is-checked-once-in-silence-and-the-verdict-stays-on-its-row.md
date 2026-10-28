---
status: accepted
date: 2026-10-28
---

# A release is checked once, in silence, and the verdict stays on its row

Marcia's app verifies a release in eight ways before Refine reads it, and nothing in the API did.
The team approves and moves on, so a broken release (bytes that no longer match, a frase that
leaves its take, a splice that lost its parent) surfaced only when the consultant opened it.

Decided on 2026-10-28 (ENG-1799): after the answer to an approval, a background job with its own
session runs the eight checks and writes one verdict (when it ran, and each check by name with
pass or fail) in the release row's `release_check` column. It is stored on the row and not in the
packet, so it sits outside the hash and a version is never minted for a verdict. A release that
already holds a verdict schedules nothing on a repeated approval: one check per version, and
re-running it belongs to ENG-1802. A failing or broken check never blocks the release and no read
the team has serves it; a job that breaks leaves the column null.

Check 2 is her `verifyRelease.ts` items 5 and 6 (18fa7c4): it fails on a frase whose take is not
live, a span leaving its take by more than 50 ms, two frases of one take overlapping by more than
50 ms, or a take with no frase; an uncovered stretch of 500 ms or more is a note on a passing check.
Check 8 is hers too (`verifyRelease.ts:131-141`): the manifest's clips as (part key, take id,
sha256) in scene order must equal the pinned takes' triples, by id, so a take swapped back to the
same bytes under a new id is caught; a manifest that cannot be built is a note, not a failure.
Check 4 verifies each laid-in sentence's own object against its digest, and that both takes it
joins still exist.

Rejected: building the manifest in the job (it signs a link per take against the bucket, and a
bucket outage would lose the whole verdict), and a column per check. Consequence: the column is
null on every release approved before this deploy.
