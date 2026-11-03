---
status: accepted; amended by ADR 0080: forced only when the gate was shut; amended 28 Oct 2026 by ENG-1776 (the team's route answers a forced release as forced)
date: 2026-10-20
---

# The force passes every blocker but a missing recording, and is addressed to the passage

ADR 0019 let the facilitator's force waive exactly two blockers, the open finding and the unheard
part, and called everything else (a telling-back missing, never analysed or untold) material rather
than a dispute; ADR 0026 kept the untold part out of the force for the same reason. Marcia's page
(her ruling of 7 September, PRD ch. 20, ENG-1305) has one force, «Aprovar mesmo assim (forçar)», and
it passes her whole gate; the one thing that still refuses it is a passage with no recording.

Decided with Jonatas on 2026-10-20: the force follows her rule. Every blocker yields to it except
`no_rehearsal_audio`. A panorama and the demo team are out of its reach by construction, not by this
rule: `panorama_sessions_never_release` and `demo_team_never_releases` are raised by the composer
before any blocker list exists, so no force ever sees them. The release records the blockers it
passed beside who forced it and when. Its check state keeps `_check_status`'s rule (ADR 0020):
`status` says whether the check ran and came out clean, `forced` says whether a person passed the
gate, `forced_blockers` says what was passed. A force over a check that was not clean reads
`forcada`; a force over a clean check, where only the listening stood in the way, reads `conferida`
with `forced` true and the listening among the blockers passed, because calling a check that ran
`forcada` would report it as one that did not. Her page records that last case as an ordinary
approval (a force over a conferida translation, ruling of 7 September; her page never offers the
force there); we keep `forced` true and the blocker named so that the listening passed over is on
the record, which is the one place this ADR records more than she does. The force is addressed to
the passage, like the Zerar: the server picks the passage's live session that holds rehearsal takes,
the most recently active if there are several. The team's route cannot force, and a new
draft is refused there while any blocker stands. Asked again over content a facilitator already
forced, it answers that release marked forced, naming the blockers it was forced past. Approval
stays the team's act and forcing the facilitator's.

The packet records the force as the row does. Who forced it, when and the blockers it passed
travel in the **Check block** beside `forced`, as `forcedBy`, `forcedAt` and `forcedBlockers`:
our names, not Marcia's, in the one block ADR 0020 otherwise keeps in hers. They are outside
the hash, so forcing unchanged content still returns the release that exists, and null when
nobody forced. `forcedBy` is the Desk user's id. They are added keys, so the schema version
does not move (ADR 0020).

Consequence: a release with untold or unanalysed frases can reach Refine, marked forced and naming
what it passed. That is the facilitator's responsibility, taken in person, which is the whole point
of her force; a passage that cannot be forced stays stuck for good, which was the defect.
