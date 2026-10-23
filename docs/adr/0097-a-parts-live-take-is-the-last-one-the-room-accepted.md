---
status: accepted
date: 2026-10-23
---

# A part's live take is the last one the room accepted

ADR 0090 chose a part's live take by its **Recording time**, with the pass breaking a tie and a
take with no time of its own keeping the pass order. A tablet's clock can read any year, so a
take stamped 2099 would hold its part against every later recording and a take stamped 2000
would never become it. This supersedes in part ADR 0090.

Decided (ENG-1760, the Definer's recon Q69, chosen by Henok on 2026-10-23):

- Under one part number the live take is the last one the room accepted: the takes read by
  ordinal, then arrival (`created_at`), then id. Neither the pass nor the Recording time orders
  a rehearsal take, and rows stored before this change keep their arrival order.
- The Recording time is the record for the consultant and Refine (ADR 0072). It orders nothing
  and is never clamped or corrected, so the derivation of which takes have one of their own,
  and a splice inheriting it from the part it was laid into, are gone.
- A back-translation take still reads by its pass before arrival: its pass says which side of a
  check it was told on, not how many times a tablet recorded.
- What ADR 0090 decided about stretches stands: a stretch counts only on the take that is the
  part now, a stored check stands only while every stretch it read is on a part, and findings
  on a take that stopped being the part are stored and never carried. Rows told and checked
  under the earlier orders are exactly the case where the part changes with nobody recording.

Rejected: **ordering by Recording time** (ADR 0090), for the broken clock above. Her app keeps
an order clock floored at the live take's plus one millisecond, so the order of acceptance is
the order she reads, and `created_at` already is it.

Consequences: a take that drains late from a tablet's outbox is the part when it lands, even
when the team recorded over it meanwhile (ENG-579's case); a join names the take it replaces
and is refused when that take is no longer live (ENG-1385). A session whose earlier order and
arrival disagree changes its part once, so its packet's hash moves once and its stored check
reads as not checked until the team tells and checks again.
