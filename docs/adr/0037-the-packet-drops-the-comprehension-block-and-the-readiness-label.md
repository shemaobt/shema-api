---
status: accepted
date: 2026-09-24
---

# The **Packet** drops the comprehension block and the readiness label, and moves to v0.7

The packet carried a `comprehension` block — an outcome, the supported units, the practised
scenes, the evidence events and their open points — and a top-level `readiness` that always said
`ready_for_refine`. Both were ported from Marcia's August branch, and neither is in her
September line: her Refine manifest carries neither, and her letter of 04/09 says why the
machinery behind them is gone: "O Assessor e o contrato de sonda não existem mais. Quem confere o
reconto é o Guia, item por item contra o mapa, com a conversa inteira em contexto." In this room
nothing has written the evidence registry since 08/09, and after the practice credit left, every
new packet would have said `needs_more_work` in its block beside `ready_for_refine` at its top.

Decided: the block, the label and the open points' term in `open_questions` leave the packet,
which now counts the unresolved raised questions and the findings still open, and nothing else.
`SCHEMA_VERSION` moves to v0.7: a consumer diffing the two versions finds two keys gone and
nothing renamed, the shape ADR 0017 and ADR 0022 set for the same kind of change. The
`ir_sessions.comprehension` column stays as it is, neither dropped nor rewritten; the room stops
writing it and nothing reads it. A packet already approved stays at v0.6 with both keys, served
as stored (ADR 0014), and a reader tells the two apart by `schema_version`.

The consumers were checked. Refine is the known consumer of the schema version. The Desk reads
the whole packet through the facilitator's release route, the tablet reads only the approval's
`release_id`, `version` and blockers, and nothing in this repository, in tripod-console or in the
internalization-room app reads any of the removed keys.

Consequence, decided knowing the price, the one ADR 0022 paid for v0.6. The hash covers the whole
content, so `package_sha256` moves for every packet. After the deploy, the Desk reads a session
approved before it with `release_id` and `version` null until somebody approves it again. That
first re-approval of an already released passage mints a **Version** whose content differs only
by this bump, and a new **Version** starts with zero listeners on Marcia's external check. A
draft a facilitator forced over a finding that is still open is judged again on that
re-approval, and only a facilitator's code lets it through a second time (ADR 0019).
