---
status: accepted
date: 2026-10-23
---

# A grain switch stamps the earlier grain's takes aside, and the parts are the newest grain's

Until now a take with no number stepped aside whenever a numbered part existed (ADR 0023), so a
team that recorded by scene and then chose to record the passage whole could never make its
whole take stand. Marcia's app lets the team switch between the two grains: the switch archives
the earlier recording, never deletes it, and starts the telling-back over when there was one
(`grainSwitch.ts` at 18fa7c4). ENG-1765 brings that rule to the server.

Decided (the Definer, 2026-10-22, recorded on the ticket):

- The team switches through the grain door, `POST /sessions/{id}/grain` with `grain` `whole` or
  `scene` (her wire values). The session keeps the grain in force and when the switch reached
  the server. A switch to the grain in force changes nothing and answers 200.
- A real switch stamps every rehearsal take the session holds with the switch's time
  (`set_aside_at`): the earlier grain's parts, their superseded takes and a whole that had
  already stepped aside. The stamp is set once and never cleared, so a switch back restores
  nothing.
- A stamped take is no **Part**, whatever its number. After a switch the parts are the new
  grain's takes recorded after it, so a whole recorded after a switch to the whole passage is
  the one part beside numbered takes the switch stamped.
- A take of the earlier grain that lands after the switch (the Outbox drains by part) is kept
  and stamped with the latest switch's time at once. It is never refused: a refused Outbox row
  is refused for good on the tablet. Over an approved draft ADR 0081's guard refuses only a take
  that would become a part, so such a take is never refused there either: it changes no draft
  (the Orchestrator, 2026-10-23).
- The telling-back starts over as «recomeçar a tradução» does, so the passage has no check and
  the automatic check runs again. A switch over nothing told starts nothing over, so no empty
  attempt is shown to the consultant.
- Over an approved draft without `reopens_the_approved_draft` the door refuses `DRAFT_APPROVED`
  (409) and nothing changes (ADR 0081).
- Nothing is deleted: the takes listing, the **Retroverification file** and the take downloads
  list the stamped takes with `set_aside_at`.
- Three nullable columns, no backfill: «no migration» in the ticket means no migration of stored
  sessions. Every stored row reads as never switched.
- The switch writes the session's row by compare-and-set and takes no `FOR UPDATE` (ADR 0089).
  It sweeps the earlier grain once more after its commit, for a keep that committed its take
  while the switch ran and read the session before the switch committed.

Rejected:

- `current_parts(takes, switches)`, reading the switch off the session: every reader of the
  parts would have to pass it, and one that forgot would serve a set-aside take as a part.
- Refusing a take of the other grain, as her keep does (`grain_mismatch`): the ticket sets it
  aside, and a refused Outbox row is refused for good.
- Comparing **Recording times** with the switch instead of stamping: a joined part keeps the
  server's clock and a tablet take its own (ADR 0072), and five minutes of drift would put a
  take on the wrong side.
- A table of switches beside the scene restarts: one grain in force and one time per session is
  all a door or a reader asks, and each stamped take carries its own switch's time.
- A `FOR UPDATE` on the session: the sentence door's write stays the only one (ADR 0089).

Consequences:

- `grain_mismatch` is not the server's.
- A take of the new grain recorded before an earlier switch (two switches back) and landing late
  is not stamped. Ordered by Recording time, the take recorded after the latest switch stays the
  part and the late one reads as superseded; ordered by pass, the late one could stand if its
  pass is higher. It only happens to a tablet that kept a row across two switches.
- The app's ADR 0102 ("the moment the first scene part lands it is set aside") holds only for a
  session never switched; the tablet half (ENG-1766) amends its status line.
