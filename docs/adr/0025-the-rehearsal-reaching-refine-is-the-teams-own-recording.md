---
status: accepted
date: 2026-09-17
---

# The rehearsal reaching Refine is the team's own recording, never one the server assembled

Marcia ruled on 07/09 that what the team records again is the unit it rehearsed and chose before
recording, the scene or the whole passage, never a stretch defined afterwards by a listening
pause; and that the recording reaching Refine is "o ensaio de vocês contado inteiro, não um
arquivo montado". Until now the room offered a microphone on one stretch of the mother tongue,
the server took a `replace` without audio as that fragment arriving, kept it as a rehearsal take
with no part number, and assembled a new passage around it with ffmpeg, the **Rebuild**, which
every stretch of the replaced recording was then re-pointed at; a rule capped a stretch at two
corrections so the third could not move the slice again.

Decided: the per-stretch mother-tongue correction and the rebuild are removed, not repaired.
One **Correction** remains, the same stretch told again over the recording it already sits in,
so `replace` takes audio and never nothing, and the two-corrections rule goes with the path it
guarded. An error in the recording is answered by recording the **Part** again in place (ADR
0023), which retires that part's stretches and nothing else. The **Packet** carries one
recording per part, the newest, all of them performed by the team; a reader of it resolves a
stretch against a part and never against a file the server built.

Rejected: keeping the assembled file and describing it in the packet as a stretch plus an
assembly rule, which she refused by name (it breaks the frases' seconds, the hash per part and
the frozen frases of the External Check, and gives *frase* two meanings); giving the correction
fragment a part number so the packet could tell it apart, which ADR 0023 shows would fire the
re-recording verb on the very stretch being corrected.

Consequences, decided knowing them. Code that worked and was well tested leaves: the tablet's
mother-tongue station, `compose.py`, `composed_take_id` and their tests (ENG-845, ENG-853).
Rows already stored, fragments and composed takes alike, stay as history and flow through the
packet by the same rule as any take. A long passage recorded whole still costs the whole
recording when one scene is wrong: her honest cost, and the facilitator's runbook, not a screen,
is the mitigation.
