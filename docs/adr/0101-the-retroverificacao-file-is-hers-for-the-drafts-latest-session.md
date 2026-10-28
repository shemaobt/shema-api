---
status: accepted
date: 2026-10-28
---

# The retroverificação file is hers, for the draft's latest session

Until now the file carried our own fields and a notice per passage, one block per session
(ENG-892, ENG-1798). Marcia's `retroExport.ts` at her freeze 18fa7c4 has seventeen top-level keys
and about ninety field names, and the consultant reads them. Decided for ENG-1801, the Definer's
rulings of 2026-10-27 and 28:

- The file is her file, in her order, for the draft of the passage: the team's latest session in
  the live archive, or the archive named. No key of ours is served, and a key with no stored source
  is left out: `retiredBelow`, `restartedAt`, `splices` and `inserts` (ENG-1285 adds the last two).
- `clipKey` is the Part key and `idx` the stretch id, in frases, history and findings. The take id
  appears only as `supersededTakes[].takeId`. No `origin`: our join carries no scene frase.
- `version`, `releaseId`, the file's name and the `supersededTakes` file names carry one number,
  the one `take_downloads._release_id` names (ADR 0081): the draft's release, the next version of a
  reopened draft, 1 for a draft never approved, and for an archive its release or the zerada stamp
  with version 1. Her own number (`finalizeCount`) gave way to that rule.
- An approved frase keeps its number and place and finds its live stretch by its `idx`: the stretch
  itself while current (a divided one with its own words), else the one that took its place, else
  after a restart the top stretch of its part starting where it did; with none, it is empty and
  stale. A restart or a correction leaves the version standing (ADR 0081).
- The history lists every stretch ever told, abandoned ones included; `superseded` is true only
  when a replacement took the place. A frase or a line names only a predecessor that was itself
  told. Stale frases of a draft not approved follow the told ones, numbered on.
- `supersededTakes` is the draft's replaced takes only. A grain switch archives the whole earlier
  life, named as one `previous` entry (the moment, the grain abandoned). `supersededAt` has one
  source, the stamp ENG-1256 adds; until then the key is absent, never derived.

Rejected: keeping the old builder beside the new file (Henok: remove, do not keep); matching an
approved frase to a stretch by counting (a split renumbers and a number is not an address).

Consequences:

- The Desk, which read the old fields (releases, hard-stretch marks, per-part listening, nuances,
  superseded attempts), reads the release and the session retro for them from now on.
- ENG-1256 fills `supersededAt` in the file and in the download list.
