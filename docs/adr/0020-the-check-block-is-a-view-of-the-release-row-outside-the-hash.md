---
status: accepted
date: 2026-09-15
---

# The check block is a view of the release row, outside the hash

Marcia's Refine manifest carries a `check` block (version, status, forced, heardComplete,
lastCheckAt, findings, retroUrl) and asked us to sign the same names. Two of its facts, the
force and the version, live on the `ir_releases` row, which is written after the **Packet** is
built and hashed; and ADR 0014 mints a **Version** only when the hashed content changed, which
ENG-937 extends to the team's approval after a facilitator's force returning the release that
exists.

Decided: the block sits beside `package_sha256`, `release_id`, `version` and `created_at`,
outside the hashed content, stamped by the approval from the row it writes, served as stored
by the read by version, and derived from the live state with `version` null on the live
facilitator read. `status` is derived once from `checked` and the force. The block uses her
names verbatim (`idx` is our `segment_id`, `clipKey` our `take_id`, `frase` the frozen number),
and no schema version is bumped for an added key.

Rejected: putting the block inside the hashed content, which would make a forced packet and
the team's unchanged packet hash differently and so mint a version for nothing; and a block
without `lastCheckAt`, which would have left her format with a hole. Consequence: the
telling-back state gains `checked_at`, written where `checked` is written, null for sessions
checked before this deploy.
