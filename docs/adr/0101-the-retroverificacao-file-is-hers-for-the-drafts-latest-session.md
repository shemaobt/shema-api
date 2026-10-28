---
status: accepted
date: 2026-10-28
---

# The retroverificação file is hers, for the draft's latest session

The file carried our own fields and a notice per passage, one block per session (ENG-892,
ENG-1798). Marcia's `retroExport.ts` at her freeze 18fa7c4 has seventeen top-level keys and about
ninety field names, and the consultant reads them. Decided for ENG-1801, the Definer's rulings of
2026-10-27 and 28:

- The file is her file, in her order, for the draft of the passage: the team's latest session in
  the live archive, or the archive named. No key of ours is served, and a key with no stored source
  is left out: `retiredBelow`, `restartedAt`, `splices` and `inserts` (ENG-1285 adds the last two).
- `clipKey` is the Part key and `idx` the stretch id; the take id appears only as
  `supersededTakes[].takeId`. No `origin`: our join carries no scene frase.
- `releaseId` is the name `take_downloads._release_id` gives (ADR 0081). `version` is always read
  from the release column, never parsed from the name (a release stored before ADR 0048 is named
  by its row id): the standing release's own, else the passage's latest plus one (the counter is
  numbered within the pericope and the team, in the live draft and in an archive alike, as the
  download list reads it), 1 when there has never been one, a zeroed passage included.
- An approved frase keeps its number and place and finds its live stretch by its `idx`: the stretch
  itself while current (a divided one with its own words), else the one that took its place, else
  after a restart the top stretch of its part starting where it did; with none, it is empty and
  stale. A restart or a correction leaves the version standing (ADR 0081).
- The history lists every told stretch, abandoned ones included; `superseded` is true only when a
  replacement took the place. Stale frases of a draft not approved follow the told ones.
- `supersededTakes` is the draft's replaced takes only. A grain switch that set something aside
  archives the whole earlier life, named as one `previous` entry. `supersededAt` has one source,
  the stamp ENG-1256 adds; until then the key is absent, never derived.

Rejected: keeping the old builder beside the new file (Henok: remove, do not keep); matching an
approved frase to a stretch by counting (a split renumbers and a number is not an address).

Consequences:

- The file lists the checks of the live record only: her restart archives the record and drops its
  frases and checks (`bt/restart/route.ts:3-6`), so ours does the same, as Henok decided on
  26 October. The findings of superseded attempts stay in the database for ENG-1343.
- The old file's other data (the releases listing with who forced, hard-stretch marks, per-part
  listening, nuances) is served by no route now; the Desk never read the file.
- An archive zeroed before a later release reads the later number as its version, and its name
  carries the zerada stamp, not a number.
