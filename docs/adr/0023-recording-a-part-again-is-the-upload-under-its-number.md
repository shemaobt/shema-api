---
status: accepted
date: 2026-09-16
---

# Recording a **Part** again is the upload under that part's number

Until now the only verb that retired stretches was the telling-back started over, which retires
every stretch of a session at once because the team threw the whole recording away. A team that
re-records one scene of a rehearsal was answered by that verb or by nothing: ENG-861 is the
report of the first, and the tablet's own gesture was the second — it uploads `parte-N+1`, so a
re-recorded part landed as a new part at the end and the old one went on counting.

Decided: a rehearsal take stored under a number an earlier rehearsal take of the session
already carries **is** that part recorded again, and storing it through the tablet's upload
route retires the stretches whose recording is one of those earlier takes — divided parents and
their pieces alike — and nothing else. The findings that pointed at them go with them, a
**Swap** whole (ADR 0018 keys the join on the **Chunk**, so a swap's two halves can sit on two
parts and half a swap is not a thing the team can be asked about). `checked` goes false and the
stored verdict goes with it, on the precedent of the retired evidence kind: a verdict the room
would serve again is about a reading of a passage that has changed. The stretches become
**Abandoned** rows, which the **Packet** carries in `superseded_segments` and the
**Retroverification file** in `abandoned`; the file keeps a link to every take, the replaced one
included, and it is where the history is read.

**The identity of a part is the take's `ordinal`, never its scope string.** The tablet sends
`parte-N` and the number beside it, and the text seam declares every part it has under the
pericope as scope: keyed on the string, a seam session would be one part and a re-record would
retire the whole rehearsal. Zero is a number, and the seam's parts start there.

**The verb is the route and not `store_take`.** Storing is a primitive with two other callers,
and one of them is the **Rebuild**: it stores a passage assembled around a corrected stretch,
carrying the number of the recording it was built from, and it then re-points those very
stretches at the file that came out. Retiring inside the storing would take away the stretches
the rebuild exists to keep. The seam's `declare_rehearsal_parts` is untouched for the same
reason.

**The newest under a number is the last of them in reading order** — the pass the tablet
counted, then the moment the upload landed — and not the moment alone. That stamp is when the
upload landed, and the outbox drains whenever the link comes back, so the rehearsal that arrives
last is sometimes the one the team abandoned; the pass is the tablet's own count of its own
recordings and does not move with the link. The same reading answers what fires the verb: an
upload that is *not* the part now is a stale retry, and reading it as a re-recording would
abandon the part standing and take the check with it.

The **Packet** then says which takes the rehearsal is: one per number, the newest, and
`recording_grain` reads `parts` when any current part carries a number and `whole` when none
does. Listing every rehearsal take sent the recording the team abandoned to Refine beside the
one that replaced it under labels that told them apart by nothing (ENG-579), and the grain was
the literal `"whole"` (ENG-642), which described a rehearsal told in five parts as a file that
never existed. `no_rehearsal_audio` goes on reading every rehearsal take: whether anything was
recorded and which recording is current are two questions.

Rejected: **an explicit route** the app would call before the upload, which is a second thing
that can fail between two calls the tablet already makes as one, and a contract to keep for a
fact the upload already carries. **The scope string as the key**, for the seam above.
**Renumbering the other parts** on every re-recording, which ADR 0021 rejected when it made the
reading order the part's number and then the milliseconds; this decision is what that order was
written for. **Deriving the listening gate's parts from the takes table** rather than from the
stretches, which would have answered a question the takes cannot: `created_at` is when an upload
landed and the tablet's outbox drains whenever the link comes back.

`SCHEMA_VERSION` does not move. No key arrives or leaves the packet and none is renamed: the two
keys under `audio` keep their meaning and start telling the truth, which is the shape ADR 0018
carried without a bump. The hash does move for a session holding a take it had abandoned, so the
next approval of such a passage mints a **Version** whose content differs by that; that is the
same price ADR 0018 named and took.

Consequence, decided knowing it. `already_analysed` compares the addresses of the reading in
order, so a re-recorded part moving into its place is a reading the analyst has not done and the
next *terminei* pays for a whole re-read. It is the right answer — the passage the team is
standing on is not the one that was read — and it is written here so the next person does not
read the extra reading as a defect.

Two things this does not close, both of them about a number the tablet does not send. Two
uploads of one part carrying the *same* pass, drained out of order, still pick the one that
landed last: the pass separates a recording from the one it replaced, and it cannot separate two
the app counted alike. And a mother-tongue correction take is a rehearsal take with no number at
all, so it is a part of its own here — in a session told in parts it is listed beside them, and
in one told whole whose rebuild failed it is the newest of the unnumbered group and the packet
names the fragment as the rehearsal, with its stretch reading first. Both want the correction
take to carry the number of the part it corrects, the way the rebuilt passage already carries the
number of the recording it was built from, and that is the tablet's contract rather than this.
