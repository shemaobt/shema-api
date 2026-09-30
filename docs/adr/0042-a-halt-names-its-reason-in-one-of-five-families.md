---
status: accepted
date: 2026-09-30
---

# A halt names its reason in one of five families

The tablet asks for a person at about fourteen places (a device the server refused, three failed
calls in a row, a Guide clip that would not play three times, a recorder that would not start, a
take with no audio, a room that stayed thinking past its ceiling, a session gone with no way to
resume, a resume that failed, a wheel with no passage that opens, a back-translation with no
parts, an approval the tablet cannot place), and the ask carried no reason: the Desk could say
only "the room stopped" and since when.

Decided by Henok on 2026-09-30 (the Attention page): the ask carries a **Halt reason** in one of
five families, `DEVICE_REFUSED`, `ROOM_FAILED`, `SOUND_FAILED`, `SESSION_LOST` and
`INCONSISTENT`, minted by the tablet at the place that raises the halt; the server stores it
beside the halt kind, answers it on every row that says a halt stands, and answers
`HARD_STRETCH` for a warning, which only the server raises. The reason is optional on the wire:
a tablet that names none, or a family the Desk does not know, reads as "the room stopped". It
is never cleared, like the halt kind: it is the reason of the last halt.

Rejected: one code per situation (fourteen sentences in three languages for distinctions the
facilitator does not act on differently); free text from the tablet (no glossary, no
translation, no test).
