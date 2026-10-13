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

- Tables of their own: `ir_scene_rehearsals`, `ir_scene_frases` and `ir_scene_restarts`. The recording
  is not a third take kind in `ir_takes`: every reader of that table (the takes lists, the
  current parts, the archive snapshot, the packet) would read it as a passage **Part**. The
  bytes still go through the take store, content-addressed.
- A **Restart** is a numbered row with the record's snapshot, and the frases it sets aside
  carry its id. Zerar stamps the scene tables with its **Archive** like the five before them
  (ADR 0047). A frase that lands while its rehearsal is archived carries the same stamp.
- The tablet mints each restart's attempt id, a uuid, and sends it with the restart and with
  every frase recorded after it; the first attempt names none. The server keeps it as the
  restart's id, which makes the same restart sent twice the first one. A frase of an attempt
  a later restart closed is kept, set aside by that restart, never current. A frase naming an
  attempt whose restart has not landed yet is held, in no list, until that restart lands and
  makes it current. A restart and a frase landing take the rehearsal's row lock, so one
  always reads the other, and each takes the rehearsal's archive stamp if a Zerar got there
  first.
- The tablet's doors carry no words of the team and no classifier guess (ENG-1335). The
  frases' words, each restart's snapshot and every frase it set aside, the late ones
  included, and the guess are the reader door's, which reads a session its Zerar archived
  (ADR 0052).
- The tablet's list covers the whole passage across its live sessions and names each item's
  session and its `n`, numbered per session, so a new session sees the passage's live
  rehearsals before any turn. A sent rehearsal refuses new frases and restarts with 409.
- A frase may name any version of the frase it replaces: an offline tablet can only name the
  version it had, so the server replaces that chain's current frase.
- `ir_sessions.kept_takes`, written only as `{}` and read by nothing, is left out of the
  mapper and defaults to `{}`, so no statement names it. A later migration drops it once no
  revision still serving reads it: the deploy migrates before the new revision takes traffic.

Rejected: copying the record into archive prefixes as her file stores do, for the reason ADR
0047 gives, and a loudness-envelope route, since the tablet draws from the bytes it is served.
