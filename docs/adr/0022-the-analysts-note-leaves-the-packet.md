---
status: accepted
date: 2026-09-15
---

# The analyst's note leaves the **Packet** and lives only in the **Retroverification file**

The **Analyst** answers with a sentence about the telling-back, and that sentence cites internal
rule ids and uses words Marcia banned from the team's ears. It travelled in the packet, which is
the artifact Refine reads, and Refine is where the team works. She confirmed the rule on 08/09
and, usefully, said where the note *does* belong: "The analyst's note goes **only in the
consultant's file**, never in the Refine manifest."

Decided: a **Finding** in the packet is a kind and an address and nothing else, in
`back_translation.findings` and in the superseded attempts' findings alike, through one view so
the two cannot drift. The note keeps a reader — the **Retroverification file**, which is the one
artifact written for somebody allowed to see internal rule ids — and `ir_releases.forced_open_findings`
keeps its own copy, dumped from the state the packet was composed from rather than copied out of
the packet's list, because a facilitator asking what was overruled is asking the consultant's
question. `SCHEMA_VERSION` moves to v0.6: a consumer diffing the two versions finds one key gone
from every finding and nothing renamed, which is the shape ADR 0017 set one version back for the
same kind of change.

Rejected: leaving the note in the packet and relying on Refine not to show it. It puts the rule
in a product this repository does not own and cannot test, on a field that is already in the
artifact by the time anybody could decide not to render it — and a second consumer of the packet,
or a support engineer reading the JSON, is outside whatever Refine chooses to draw. A rule about
who may read a sentence is kept by not sending the sentence.

Consequence, decided knowing the price. The hash covers the findings the packet dumps, so
`package_sha256` moves for every packet: the first re-approval of a pericope already released
mints a **Version** whose content differs only by this bump and the removed note, and a new
**Version** starts with zero listeners on Marcia's external check (ADR 0014). It is the same
price v0.4 → v0.5 paid, and the alternative — carrying a key downstream that no longer means what
it said — is the one ADR 0014 rejected by name.
