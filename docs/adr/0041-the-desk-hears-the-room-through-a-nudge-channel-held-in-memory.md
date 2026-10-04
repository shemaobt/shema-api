---
status: accepted
date: 2026-09-30
---

# The Desk hears the room through a nudge channel held in memory

The Desk re-read nothing on its own: a new hand, a halt, a take or a session's end reached the
facilitator only on a reload. Three shapes were on the table: polling every 30 s, Server-Sent
Events with a registry in memory, and Server-Sent Events with a broker between API copies
(Memorystore, Pub/Sub or Neon LISTEN/NOTIFY, which does not pass the pooler).

Decided by Henok on 2026-09-25 and settled on 2026-09-30 (ENG-1124, ENG-1127, ENG-1132): one
stream per team, the shape of the tablet's coverage channel, and a **Nudge** on it whenever a
route writes something the Desk shows. A nudge names what changed and carries no data; the Desk
reads that thing again through the routes it already has, and reads everything again when the
stream reconnects or the facilitator returns to the tab. The registry lives in memory, one per
team, and holds while the API runs in one copy, which it does today (min 1, no max, CPU always
on). The API's request timeout rises to 3600 s for the stream.

Rejected: polling, because the Desk would read the same answer every 30 s and Henok wants the
Desk driven by what happens in the room; a broker now, because it is a second service for one
API copy. A broker is the recorded next step, the day the API runs in more than one copy; the
registry's interface is the seam it replaces.
