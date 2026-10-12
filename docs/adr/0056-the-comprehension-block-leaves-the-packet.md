---
status: accepted
date: 2026-10-08
---

# The comprehension block leaves the **Packet**

The packet carried a `comprehension` block: the readiness the room computed from its own
reading of the conversation, the scenes it had credited as practised, the evidence ledger and
the ledger's open points, which also counted among `open_questions`. All of it came from
machinery her room does not have — a regex that credited practice when the voice's line read
as an invitation and the team's next words as a report, and an evidence ledger nothing has
written since 8 September. ENG-1303 removes the machinery: the voice speaks from her prompt
alone, and a passage is done at the coverage floor. With nothing writing the session's
comprehension column, every new packet would have said `needs_more_work` beside
`ready_for_refine`.

Decided: the block goes, and its open points leave `open_questions`, which now counts the
raised questions still open and the findings the telling-back still carries. `SCHEMA_VERSION`
moves to v0.7: a consumer diffing the two versions finds one key gone and nothing renamed,
the shape ADR 0017 set. The column stays on the session row, unread and unwritten, so a
session that holds that history still opens, takes a turn and releases. Approved v0.6 packets
stay as they were stored (ADR 0014).

Rejected: keeping the block with whatever the column last held. It would carry a reading the
room no longer makes, and an empty one would tell Refine that no scene was practised.

Consequence, decided knowing the price. The hash covers the block, so `package_sha256` moves
for every packet: the first re-approval of a pericope already released mints a **Version**
whose content differs only by this bump and the missing block, and a new **Version** starts
with zero listeners on Marcia's external check (ADR 0014). It is the price v0.5 and v0.6 paid
(ADR 0017, ADR 0022).
