---
status: accepted
date: 2026-10-13
---

# A scene rehearsal is its own record, and its restarts and Zerar stamp it and move nothing

In Marcia's app a **Scene rehearsal** is a folder per session: the scene recording, a record of
its translated frases, and dated `archive/` copies made by «recomeçar a tradução» and by Zerar.
Our room had nowhere to keep one, and the team must resume an unsent rehearsal from any tablet
(ENG-1312).

Decided with the Definer on 2026-10-13:

- Tables of their own, starting with `ir_scene_rehearsals`. The recording is not a third take
  kind in `ir_takes`: every reader of that table (the takes lists, the current parts, the
  archive snapshot, the packet) would read it as a passage **Part**. The bytes still go
  through the take store, content-addressed.
- Zerar stamps the scene tables with its **Archive** like the five before them (ADR 0047).
- The tablet's doors carry no words of the team and no classifier guess (ENG-1335).
- The tablet's list covers the whole passage across its live sessions and names each item's
  session and its `n`, numbered per session, so a new session sees the passage's live
  rehearsals before any turn. A sent rehearsal stays listed and can still be heard.
- `ir_sessions.kept_takes`, written only as `{}` and read by nothing, is left out of the
  mapper and defaults to `{}`, so no statement names it. A later migration drops it once no
  revision still serving reads it: the deploy migrates before the new revision takes traffic.

Rejected: copying the record into archive prefixes as her file stores do, for the reason ADR
0047 gives, and a loudness-envelope route, since the tablet draws from the bytes it is served.
