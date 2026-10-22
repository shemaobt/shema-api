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
- **Only for a draft approved as it stands.** "Approved" is ADR 0071's one answer. Otherwise the
  read is 409 `DRAFT_NOT_APPROVED`, its own code because there is no version to reload and no
  blocker to name.
- **The packet is the record.** It is still composed, hashed and stored on the release row, and
  `GET /facilitator/sessions/{id}/releases/{version}` still serves it verbatim. No route serves it
  live any more.
- **Clips are the current parts** that have bytes, keyed by **Part key**, named
  `<releaseId>-<key>.<ext>` with the stored release id (the uuid on a release stored before ADR
  0048), each with an hour-long link: the download list's names byte for byte (ADR 0073). A joined
  part carries her five `origin` keys, with `joinedAt` the server's time the part landed. A part
  with sentences laid in carries `splices`, counted along its chain from take to take. The
  **Clock offset** and the order clock never enter.
- **The meaning map is read at the session's pin**, from the sync's own record
  (`VENDOR_MANIFEST.json`), so a session opened before a re-pin names its kept pin and its kept
  file's fingerprint. `file` is our vendored path.
- **`check` is the stored check block in her keys**: `nuances` only when any stood, `retroUrl`
  always, and never who forced it, when, or what the force passed. Its findings and nuances keep
  ADR 0078's shape.
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
