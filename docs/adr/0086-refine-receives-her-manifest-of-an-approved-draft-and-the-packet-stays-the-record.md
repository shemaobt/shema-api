---
status: accepted; amends ADR 0014
date: 2026-10-22
---

# Refine receives her manifest of an approved draft, and the packet stays the record

The Desk's release read served Refine our live **Packet**: a document of our own design that
carried the frases' words, the analyst's notes, the comprehension of the questions, superseded
attempts and bridge-language takes, and that lacked most of the fields of Marcia's manifest
(`src/draft/export.ts` at her freeze 18fa7c4). Refine could not be built against it as against
hers, and it handed Refine the consultant's material.

Decided (ENG-1274):

- **The release read serves the Manifest.** `GET /facilitator/sessions/{id}/release` answers her
  document field for field and in her order: `releaseId`, `pericopeId`, `reference`, `language`,
  `sessionLanguage`, `meaningMap`, `grain`, `clips`, `finalizedAt`, `finalizeCount`, `sessionIds`,
  `audioFormat`, `whole` (when one exists; never yet), `integrity`, `externalCheck`, `check`,
  `warnings` (when any), `exportedAt`. Its gate and its scoping do not change.
- **Only for a draft approved as it stands.** "Approved" is ADR 0071's one answer, and the
  parts the manifest lists must be the very takes that approval judged, fingerprint for
  fingerprint: a part recorded again between the two reads makes the draft unapproved, never a
  clip. Otherwise the read is 409 `DRAFT_NOT_APPROVED`, its own code because there is no version
  to reload and no blocker to name. A session whose kept canon is gone is never told it is not
  approved: the read answers `CANON_NOT_KEPT`.
- **An approval stored in an older shape stays an approval.** Whether a stored release is this
  draft compares only what the stored packet and the composed one both hold, and never the
  counts read off the draft (`open_questions`, which v0.6 swelled with its comprehension's open
  points), so a packet stored before v0.7 (with its `comprehension` block) or before the check
  was recorded (with no
  `check`, and so no word on whether every part was heard) still answers its manifest. The one
  with no check carries her warning that no check state was recorded. A take changed since
  still un-approves it, as it does any release.
- **A Zerar retires the approval.** An archived session's draft is not approved, so its manifest
  is refused until the passage's new session approves (its next version). The archived release
  row and its packet stay readable by version.
- **A panorama is refused before any canon is read**, as before: it has no meaning map to name.
- **The packet is the record.** It is still composed, hashed and stored on the release row, and
  `GET /facilitator/sessions/{id}/releases/{version}` still serves it verbatim. No route serves it
  live any more.
- **Clips are the current parts** that have bytes, keyed by **Part key**, named
  `<releaseId>-<key>.<ext>` with the stored release id (the uuid on a release stored before ADR
  0048), each with an hour-long link: the download list's names byte for byte (ADR 0073). A joined
  part carries her five `origin` keys, with `joinedAt` the server's time the join landed: the
  first take of the part's chain, which a laid-in sentence keeps, since the take a splice makes
  lands at its own time and carries the origin forward. A part
  with sentences laid in carries `splices`, counted along its chain from take to take. The
  **Clock offset** and the order clock never enter.
- **The meaning map is read at the session's pin**, from the sync's own record
  (`VENDOR_MANIFEST.json`), so a session opened before a re-pin names its kept pin and its kept
  file's fingerprint. `file` is our vendored path.
- **`check` is the stored check block in her keys**: `nuances` only when any stood, `retroUrl`
  always, and never who forced it, when, or what the force passed. Its findings and nuances keep
  ADR 0078's shape.
- **Her other fields, in our terms.** `grain` is her word: `scene` for a passage in parts,
  `whole`. `finalizedAt` is when this version was approved and `finalizeCount` is its
  **Version**, since her release id reads the count as the v-number. `language` is the one the
  stored packet named, or the team's **Mother tongue** read now for a release stored before ADR
  0048. `sessionIds` lists this team's sessions of the passage in the same archive: hers lists
  every session of the pericope, but ours serves many teams, and a Zerar retires a session's
  work.
- **The live composition leaves the app.** With no route serving it, the builder that composed
  and refused at once moves into the test harness; the approval still judges what the composer
  composes.
- **`integrity` says what is true here**: every fingerprint is the server's, taken from the stored
  bytes. `externalCheck` is null until the external check reaches it.

## Considered options

- A new `/manifesto` route beside the live packet read: rejected, because it leaves the packet
  served as the Refine hand-off and gives one reader two routes.
- Building the clips from the stored packet's `audio.rehearsal_takes`: rejected, because packets
  stored before v0.9 carry no `key`, and the Definition says the clips are the current parts.
- Serving a manifest with `check: null` for an unapproved draft, as her route does: rejected, the
  ticket refuses a manifest of a passage nobody approved.
- Her `integrity` sentence: rejected, it describes a direct-upload path we do not have.
- Her `_spec/canon/…` `file` path: rejected, it is her repository's path, not ours.
- 404 for an unapproved draft: rejected, the owner must be told apart from a stranger, who gets 404.

## Consequences

- The Desk's live read of a ready but unapproved packet is gone; no client read it.
- Refine matches clips by `takeId` and `sha256`, never by file name (ADR 0073), and its intake is
  built against this manifest. A finding's `clipKey` is the take id (ADR 0078), not her scene key.
- A manifest's links last an hour: read it again for fresh ones.
- What the manifest leaves out is the consultant's and is in the **Retroverification file**; the
  raised questions stay in the stored packet.
