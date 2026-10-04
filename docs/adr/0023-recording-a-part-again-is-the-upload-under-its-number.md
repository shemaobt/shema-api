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

**The verb is the route and not `store_take`.** Storing is a primitive that knows nothing of parts:
its two other callers keep the tellings of a stretch, and a verb inside it would run on every take
the room keeps. The reason first written here was the **Rebuild**, a third caller that stored a
passage assembled around a corrected stretch under the number of the recording it was built from
and then re-pointed those very stretches at it — retiring inside the storing would have taken away
the stretches the rebuild existed to keep. That caller is gone with the gesture (ADR 0025) and the
rule stands on the sentence above. The seam's `declare_rehearsal_parts` writes its rows without the
primitive at all.

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

A part whose stretches did not move leaves the check alone. Two uploads reach the verb with an
earlier take of their number and nothing to retire — the team re-sending bytes of the part that
is standing, and a part recorded twice before anybody told it back — and neither changed the
reading, so neither un-checks it.

**History, while the room had a per-stretch mother-tongue correction.** That correction arrived as
a rehearsal take carrying no number, and it could not be given one: under a number it would have
been read as that part recorded again, so the verb would have retired the very stretch the
correction was about to replace, and the call that followed would have met *this stretch no longer
counts* and lost the team their correction outright. The price of that invariant was two gaps,
recorded here as facts: in a session told in parts the fragment was a part of its own and the
packet listed it beside the real parts; in a session told whole whose rebuild failed the fragment
was the newest of the unnumbered group, so the packet named it as the rehearsal and its stretch
read first.

Both gaps are closed, and not by numbering the fragment. ENG-845 removed the per-stretch
correction itself: what a team re-records is the unit they rehearsed, and the recording that
reaches Refine is their own (ADR 0025). The tablet mints no such fragment any more (ENG-848), and
`replace` takes audio and never nothing, and a version of a stretch is refused unless it sits
where that stretch sits, so none can move onto a recording of its own (ENG-849). Nothing
unnumbered arrives that way again; the rows already stored are tolerated as history and travel
through the packet by the same rule as any other take.

Two uploads of one part carrying the *same* pass, drained out of order, still pick the one that
landed last: the pass separates a recording from the one it replaced, and cannot separate two the
app counted alike.
