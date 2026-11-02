---
status: accepted; amended by ENG-2133: a stale frase of a draft not approved is numbered in its place among the told ones, as the tablet draws it, and only a told stretch is a frase; amended by ENG-2139: a check's finding keeps the frase stored on it
date: 2026-10-28
---

# The retroverificação file is hers, for the draft's latest session

The file carried our own fields and a notice per passage, one block per session (ENG-892,
ENG-1798). Marcia's `retroExport.ts` at her freeze 18fa7c4 has seventeen top-level keys and about
ninety field names, and the consultant reads them. Decided for ENG-1801, the Definer's rulings of
2026-10-27 and 28:

- The file is her file, in her order, for the draft of the passage: the team's latest session in
  the live archive, or the archive named. No key of ours is served, and a key with no stored source
  is left out: `retiredBelow`, `restartedAt`, `splices` and `inserts` (ENG-1285 adds `inserts`;
  `splices` stays out because `LaidInSentence` stores no stamps).
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
  replacement took the place. A frase or a history line names only a predecessor that was itself
  told. Stale frases of a draft not approved follow the told ones, numbered on in sequence from the
  last, so a stale line in one part moves no other part's number.
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

**Amended on 2 November 2026 (ENG-2133): a stale frase of a draft not approved keeps its place.**
The fourth bullet above hung the stale frases after the told ones, numbered on from the last, so
above a part recorded again the file said frase 2 for the row the tablet draws, the voice says and
the check names as 3, and the old stretch came last. Her `retroExport.ts` writes the live
`st.frases` whole, in `buildPassageTelling`'s order, so the file now numbers through
`passage_numbers` — standing and stale told stretches placed by the session's takes, the standing
ones of a part before its stale ones — and lists them in that order, `stale` marking the old ones.
The check addresses read the same list. Only a told stretch is a frase: a stale piece nobody told
is no longer an empty, numbered line, as her file has no frase without a telling. An approved
frase keeps its number and place as before.

**Amended on 2 November 2026 (ENG-2139): a check's finding keeps the frase the check ran with.**
The amendment above had the check addresses of `checks[]` read the same live list as the frases,
so a finding moved with the list: a part told again after the check, or a stale row retired,
renumbered the stretch and the file named a frase the check never said. Her `retroExport.ts`
writes each check's findings as the stored object (`{...f}`), so `checks[]` now carry the `frase`
stored on the finding and on the nuance, the number the analyst named when the check ran, whatever
the list looks like at export: under an approved version too, where the version's frozen list
numbers `approval.findings` and no longer `checks[]`. A missing element placed after the last frase
carries the frase it was placed after, as hers does, where it carried none for landing on no
stretch; a finding stored with no number, a row written before the field, carries none rather than
the stretch's live number. The frases list still numbers through `passage_numbers`, and `idx` and
`clipKey` still name the stretch.
