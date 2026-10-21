---
status: accepted; amends ADR 0020
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
  downloads (ADR 0073): `whole` for a rehearsal told whole, `S<n>` for the part at position n among
  the current parts. It is read off the parts, never off the passage's map, so a part past the last
  scene is `S4` in the packet exactly as its file is `…-S4.wav`.
- **Two spellings.** A pinned take in `audio.rehearsal_takes` carries it as `key` (the ticket's list
  and ENG-1283's wire word); a frase in `back_translation.segments`, and a finding or nuance in the
  **Check block**, carry the key of the part they stand on as `scene` (the Definer's Definition).
  `scene` is absent where the stretch is not in the reading.
- **`index` is the frase number.** Present exactly when `frase` is and equal to it (the Definer). It
  is not stable across versions, since a division renumbers; `idx`, the stretch id, is the key that
  is. `clipKey` keeps the take id.
- **Nuances sit in the check block only, outside the hash.** Each is `{kind: "nuance", idx, clipKey,
  frase?, index?, scene?, voiced?}`: the standing list of the telling-back in its order, with
  `voiced` from the last check round's copy of the same nuance (same stretch, same quote), `now` or
  `before`. A last round that carried no reading (a fail-safe) erases nothing: a nuance an earlier
  heard round said reads `before`. A `now` the team never heard, followed by a fail-safe round,
  reads absent, as the retroverification file's `said` reads it. Otherwise `voiced` is absent. Never
  the quote, the story or the note (the Definer); the retroverification file keeps those.
- `scene` and `key` sit in hashed lists, so `schema_version` is v0.9. The check block's new keys
  need none (ADR 0020).
- **An approval compares the draft, not the published hash** (the Definer's option B, amending ADR
  0020). Whether a stored release is the draft composed now is read the same way off both packets,
  on the spot: the takes by fingerprint and order, the stretches, the telling with its findings and
  history, the questions, the nuances and whether every part was heard (`heardComplete`, as
  `back_translation.checked` is compared); never `schema_version`, the canon pin, the
  listening's own numbers (`played_by_take`, whose lengths are derived) nor what is read off the
  content (`key`, `scene`,
  `index`, `frase`, `duration_ms`, `voiced`, a take's other fields). Nuances are compared only where
  the stored packet recorded them. `package_sha256` stays the published hash of the whole packet, so
  Refine's check of it does not change; no column or key is added.

Rejected: **a stored stable integer per stretch**, because no column holds one and the Definer
made `index` the frase number; **`clipKey` as the scene key**, her meaning, because it would
silently change a key Refine already reads as the take id (ADR 0020); **nuances inside the
hashed telling-back**, because `voiced` moves with no content moving: a later round turns `now`
into `before`, which inside the hash would un-approve an unchanged draft and mint a version for
nothing; **the scene read off the map, with no key past the last scene**, because the packet and
the file names would then disagree about the same part; **comparing the stored
`package_sha256`**, because it moves with every schema and un-approved every draft at each
deploy; **making `package_sha256` the content's fingerprint**, because it would change how
Refine verifies the packet; **nuances always compared**, because a packet approved before they
were recorded says nothing about them, and a nuance only moves with a new reading, which only new
content brings; **the scene from a joined part's
`origin` or a scene rehearsal's label**, because the position is the house rule (the voice's
part number reads it) and a part laid in keeps its number.

Consequences: a deploy that changes the schema or re-vendors the canon, and a listen that fills
a gap the heard rule tolerated, no longer un-approve anything. A draft approved under v0.8,
forced or not, with or without a nuance standing today, still reads approved, and approving it
again answers its version. One approved under v0.7 does too, unless it held a whole recording
beside numbered parts: since 20 October the whole steps aside with its stretches and findings,
which is a different draft (measured on the commits since v0.7, not on a replayed packet). A new
take, a reordered take, a stretch told, a finding, a question or a recorded nuance still
un-approves, and so does a draft heard whole after a force: it is the team's own v2, as ADR 0019's
compare-first rule has it. Releases stored before keep their packets, and a reader treats a missing
`nuances`, `key` or `scene` as not recorded. A `voiced: now` says the verdict named the nuance;
the retroverification file's `said` counts it only once the team heard that verdict, so the two
differ for a round not played to its end, each answering its own reader.
