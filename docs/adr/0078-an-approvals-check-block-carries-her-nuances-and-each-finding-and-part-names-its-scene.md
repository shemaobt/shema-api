---
status: accepted
date: 2026-10-21
---

# An approval's check block carries her nuances, and each finding and part names its scene

Her approval record (`src/draft/store.ts` at her freeze 18fa7c4) gives every finding a
whole-number index and the scene key of the part it stands on, lists the nuances the check found
with whether the voice said them, and names each pinned take and frase by its scene key. Ours
carried the stretch id alone, no scene and no nuance, so Refine and the consultant could not
match what we hand them to her contract.

Decided (ENG-1258):

- **One key for a part.** The scene key is the **Part key** ENG-1283 already serves in the take
  downloads (ADR 0073): `whole` for a rehearsal told whole, `S<n>` for the part at position n
  among the current parts. It is read off the parts, never off the passage's map, so a part past
  the last scene is `S4` in the packet exactly as its file is `…-S4.wav`.
- **Two spellings.** A pinned take in `audio.rehearsal_takes` carries it as `key` (the ticket's
  list and ENG-1283's wire word); a frase in `back_translation.segments`, and a finding or nuance
  in the **Check block**, carry the key of the part they stand on as `scene` (the Definer's
  Definition). Both are absent where the stretch is not in the reading.
- **`index` is the frase number.** Present exactly when `frase` is and equal to it (the
  Definer). It is not stable across versions, since a division renumbers; `idx`, the stretch id,
  is the key that is. `clipKey` keeps the take id.
- **Nuances sit in the check block only, outside the hash.** Each is
  `{kind: "nuance", idx, clipKey, frase?, index?, scene?, voiced?}`: the standing list of the
  telling-back in its order, with `voiced` from the last check round's copy of the same nuance
  (same stretch, same quote), `now` or `before`, and absent when that round has none. Never the
  quote, the story or the note (the Definer); the retroverification file keeps those.
- `scene` and `key` sit in hashed lists, so `schema_version` is v0.9. The check block's new keys
  need none (ADR 0020).

Rejected: **a stored stable integer per stretch**, because no column holds one and the Definer
made `index` the frase number; **`clipKey` as the scene key**, her meaning, because it would
silently change a key Refine already reads as the take id (ADR 0020); **nuances inside the
hashed telling-back**, because `voiced` moves with no content moving: a later round turns `now`
into `before`, which inside the hash would un-approve an unchanged draft and mint a version for
nothing; **the scene read off the map, with no key past the last scene**, because the packet and
the file names would then disagree about the same part.

Consequences: v0.9 moves every packet's hash once, so every draft approved before the deploy
reads un-approved (ADR 0071) until approved again, which mints v+1; merged in the window of
v0.8 the teams see one move. Releases stored before keep their packets, and a reader treats a
missing `nuances`, `key` or `scene` as not recorded. A `voiced: now` says the verdict named the
nuance; the retroverification file's `said` counts it only once the team heard that verdict, so
the two differ for a round not played to its end, each answering its own reader. A fail-safe
last round carries no nuance copies, so no nuance has `voiced`; such a check is not conferida.
