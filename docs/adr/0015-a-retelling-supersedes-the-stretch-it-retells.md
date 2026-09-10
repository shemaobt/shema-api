---
status: accepted
date: 2026-09-10
---

# A retelling supersedes the stretch it retells, and the count of tellings lives on the row

Telling one stretch back again writes a **new version of that stretch**: the row it replaces
stops counting and names the new one as what took its place, exactly as a correction already
did through the replace route (ADR 0004). The chunks route does it too, because the tablet
sends the stretch's own address — take, start and end — back with the flag on.

How many times a stretch has been told is a column on the stretch row. A version that arrives
with a telling-back carries the count of the row it replaces plus one; a version that arrives
without one — the mother tongue re-recorded, which is answered by telling it again in a second
call — carries the count across untouched, because nothing was told into it. A telling whose
transcript came back empty captures no row at all, so it is counted in place on the row that is
standing: during a transcriber outage every attempt comes back empty, and that is precisely the
case Marcia named. The pieces of a divided stretch keep the count for the reason they already
keep the pass.

At three the stretch is a **hard stretch**, and the crossing writes one row in a table of its
own: the session, the first row of the stretch's chain, the count at the crossing, the moment.
It is written once per stretch, so the fourth telling neither asks again nor erases the record
that somebody already walked to the room, and nothing that follows clears it — not a turn that
lands, not *terminei*, not an attendance, not starting the telling-back over. No foreign keys,
matching the room's other tables (ADR 0006). Nothing on the voice path reads either the count
or the table.

Two alternatives were rejected. The first was the unchained pass-2 row the chunks route wrote
before this: a retelling appeared beside the stretch it answered, at the next position, so the
frase the team had just told again was still listed as waiting and there was no chain for a
count to live on. The second was a list inside the telling-back state, which was rejected
because starting the telling-back over rewrites that state — and surviving exactly that is what
the record is for.

The count it replaces was one integer per session. Three tellings spread over three different
frases raised the same warning as three tellings of one, and every telling from the third
onward raised it again; `mark_needs_person` clears the visit stamps on each call, so each
repeat deleted the record of the facilitator who had already come. Decided with Henok on
2026-09-10.
