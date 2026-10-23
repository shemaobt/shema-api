---
status: accepted
date: 2026-10-23
---

# An outside listener is the next number of its version, and every recording is stored before it is attached

ENG-1422 asks that each **Outside listener** of a **Checagem externa** be known by the next
number of that **Version** and nothing else, and that every recording they make be kept the
moment it stops, never heard by a recognizer or a model (the app's ADR 0111). Decided: three
tables hanging off ENG-1421's `ir_external_checks` (ADR 0082). `ir_external_listeners` numbers
each listener from 1 per check, by the room's max-plus-one loop under a unique index on (check,
number), so two tablets asking at once never share a number and none is reused. The tablet
sends an `attempt` it minted for the tap, unique per check, so a tap resent after its answer was
lost is the same listener and never leaves an empty one behind (Q70).
`ir_external_recordings` keeps each **Listener recording** (a retelling, a comment on the whole,
or a comment on one frase) with its content type, length, size, sha256 and the time it was
stored. The bytes go to the bucket under `internalization-room/external/<release row id>/<n>/`
through the takes' own store and check, and only then is the row written. `ir_external_marks`
keeps «está boa» per frase. A frase is named by its stretch's `segment_id` in the check, so a
version approved before frases were numbered can still be answered. On a check with nothing
told it is named by a part's `take_id` (her `unit: "take"`). The first finish is kept. The
newest retelling is the listener's, and the earlier ones stay stored. Four team doors write,
one team door reads a listener's facts with no audio, and a facilitator door reads everything.
None of them imports anything that hears.

Rejected: the listeners as a JSON list on the check row, her file's shape, because two tablets
at once is the read-modify-write race that hands her app a duplicate, and a unique index on rows
cannot; storing listener audio as a third take kind, because every reader of `ir_takes` reads a
team part (ADR 0059 rejected the same for scene rehearsals); a transcription flag on an existing
door, because the door that stores listener audio is a door of its own (ADR 0111); a sequence or
counter column on the check, because the house loop is proven and needs no lock; the tablet's
recording time, because the ticket keeps the time it was stored; closing the listener doors when
the draft re-opens, because the version does the work (her spec §1, ADR 0082); a frase number
on the wire, because a stretch of an older release carries none.

Consequences: listener rows and audio are kept forever, stamped by a Zerar like every row
hanging off a session (ADR 0047), and readable by the facilitator and the consultant (ADR 0052).
A recording that dies in the upload can leave an object nothing points at, never a row without
its bytes (ADR 0072). The session read's `approved.listeners` counts the listeners of the
approved version.
