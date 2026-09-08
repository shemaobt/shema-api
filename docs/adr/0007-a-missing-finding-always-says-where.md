---
status: accepted
date: 2026-09-08
---

# A missing **Finding** always says **Where**, and never null

The **Analyst** answers in JSON. For every kind but missing, a finding names the **Chunk** it
lands on and that is all. For a missing element it also gives where the absent content sits
relative to that chunk: inside, before, or after.

An element that belongs before the first thing the team told is before on chunk 1. An element
that belongs after everything the team told is after on the last chunk — never null, and never
a chunk number past the last one. That is what keeps the two kinds of absence as two different
answers rather than one answer with a hole in it: a **Missing with an address** sends the team
back to one stretch, and a **Missing without an address** sends them to record more and go back
to the **Rehearsal**, erasing nothing.

The rejected alternatives were a null where, and a chunk number one past the end, either of
them meaning "after everything". Both put the room in the position of guessing which of two
different walks the facilitator owes the team.
