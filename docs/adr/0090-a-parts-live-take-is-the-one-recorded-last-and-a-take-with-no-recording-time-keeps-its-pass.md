---
status: accepted
date: 2026-10-22
---

# A part's live take is the one recorded last, and a take with no recording time keeps its pass

The room read a part's takes by the pass the tablet counted, then by arrival (ENG-579), and the
last of them was the part. A reinstalled tablet, or a second tablet of the same team, counts its
passes from 1 again, so its newer take sorted below an older pass 2 and the team's latest take
was listed as «substituída». This supersedes in part ENG-579's pass-first order.

Decided (ENG-1760, Henok on 2026-10-22):

- Under one part number the live take is the one recorded last by its **Recording time**
  (ADR 0072). Two takes with the same Recording time are read by pass, then by arrival. A take
  recorded earlier is never the part because its pass is higher.
- A take has a Recording time of its own when the tablet sent one, and when it is a joined or a
  spliced part, whose time is the server's (ADR 0072). A take sent with no time, a declared
  text-seam part and a take stored before ENG-1273 that was neither joined nor spliced have
  none: they keep the pass order among themselves and read before every take that has one.
- The take says which it is in a stored mark, `recorded_at_known`, written when the take is
  stored and backfilled for the rows already kept: true for a joined part, for a row whose
  Recording time differs from its arrival, and for a take a laid-in sentence names. Every other
  row stays false and keeps the order it was read in until now.
- One order serves every reader: the part, the gate, the **Packet**, the listening ledger, the
  downloads' names, the tablet's list and the consultant's read. Retro takes read it too. The
  mark is never served, and the Recording time served is unchanged.
- The tablet changes nothing and keeps counting its passes.

Rejected: **pass first, with a reinstalled tablet asking the server for the highest pass**,
because it does not cover two tablets recording at once (Henok); **nulling the stored
Recording time of old rows**, because it is served on four reads and hashed into the packet
(ADR 0072), so every packet's hash would move; **guessing at read time from
`recorded_at = created_at` and no origin**, because it cannot tell a spliced part from a take
sent with no time, so a sentence laid into a tablet-timed part would sort first and stop being
the part (ADR 0069); **the stored time alone**, because a take sent with no time would go back
to upload order and ENG-579's abandoned rehearsal, written down after the take that replaced
it, would become the part again.

Consequences: tablet clocks are now compared with each other and with the server's. A tablet
whose clock runs ahead by more than the time between its recording and a later join or splice
keeps its own take as the part; the **Clock offset** is noted only for joined parts. A joined
part's Recording time is its arrival (ADR 0072), so a join that drains late from a tablet's
outbox reads after a take another tablet recorded in between, and is the part. A session
whose pass order and time order disagree changes its part once, so its packet's hash moves once
and an approved draft reads un-approved until approved again. `superseded_at` stays "when the
take that replaced it reached the server", which can now be earlier than the superseded take's
own arrival.
