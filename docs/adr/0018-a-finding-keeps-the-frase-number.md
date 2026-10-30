---
status: accepted; amended by ENG-2030: `chunk` is the position in the reading, and the number the analyst gave is read back through the reading's labels
date: 2026-09-11
---

# A **Finding** keeps the **Chunk** the analyst gave, and that is what joins a **Swap**

A telling that swaps one relation for another puts something in and drops what the story tells
in its place. The analyst reports that as two findings on one frase. Raised one at a time, the
room asked the team to record that part again for the addition and, the round after, to record
the same part again for the missing element: a second recording of one scene, for one mistake.
Marcia watched it happen in her live P02 test, and her rule is that the two are one thing.

A finding used to keep only the stretch its number resolved to. That is not enough to see the
pair. A **Missing with an address** placed *after* frase N resolves to stretch N+1 (ADR 0007),
so the two halves of one swap sit on two different stretches while being one frase's mistake.
The rejected alternative was to key the join on the resolved stretch: it is the field already
on the row, and it would have been no change at all — and it would have joined nothing in the
*after* case, which is where the defect was found. The missing element would have come back
the following round, which is the defect through the back door.

So a finding keeps `chunk`, the number the analyst gave, beside the stretch. Two consequences
were decided with it rather than discovered later:

A missing element with no stretch at all never joins. `where: after` on the last frase names
that frase and resolves to nothing, and it is a different walk: the team records what is still
missing and goes back to the rehearsal, erasing nothing. Joined to an addition on that frase,
one turn would have promised the two microphones of a stretch that is not there and asked for
one fix for two different walks. Both halves must point at a stretch.

The addition leads, whichever half the analyst listed first. It names the stretch where the
swap happened, so the closing, the request for the whole stretch, the stretch the screen puts
up and the stretch a resumed tablet rebuilds all name the same one. Led by a missing element
placed after that frase, they would have named the stretch *after* the swap. Which finding is
current is still the analyst's first: it decides *whether* there is a swap, never which half
carries the address.

Consequence: the **Correction check** is shown both lines and answers one `resolved`, true
only when the new telling dropped the addition and brought the missing element; a resolved
check clears both and an unresolved one keeps both, re-addressed to the stretch that now
counts. A row written before the field validates with `chunk` null and never joins anything.

The field travels in the packet under the schema version current at merge, with no bump, and
that was decided knowing what it costs: the packet's hash covers the findings it dumps, so a
passage approved before this deploy whose session still has a standing finding no longer
matches the release that approved it, and the packet reads `release_id` and `version` null
until the team approves again. A bump would have said the same thing to every consumer at
once, for every session, approved or not.

**Amended on 30 October 2026 (ENG-2030): `chunk` is the position in the reading.** The sentence
above says a finding keeps `chunk`, the number the analyst gave. The analyst is now shown the
numbers the tablet draws, which count the stale stretches it never sees, and its reply is read
back to a position in the reading before anything keeps it (ADR 0067). What a finding keeps is
that position; the number the voice says is derived from it on every read. Everything decided
here on the pairing of a Swap and on a missing element after the last frase holds on the
position as it held on the number.