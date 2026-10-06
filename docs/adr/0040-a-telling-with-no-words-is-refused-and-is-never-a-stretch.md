---
status: accepted
date: 2026-09-30
---

# A telling with no words is refused at the chunk door and is never a stretch

**Superseded in part by [ADR 0049](0049-a-telling-is-recognized-in-the-bridge-language-and-refused-when-nothing-comes.md)**
on 6 October 2026: an outage is now the same refusal, and the replace route no longer counts.

The chunk door answered 200 `captured: false` when the transcript came back empty, and an empty
**retelling** was counted toward the warning on the stretch being retold (ENG-706). The reason
for that count was an outage: with the transcriber down every attempt came back empty, and
leaving those free meant the team could tell one stretch forever without reaching the number
that asks for a person.

Measured, that reason was already gone. The transcriber raises `UpstreamServiceError` for an
outage (5xx, 429, 401/403, an unreachable host, a missing key), `heard` does not catch it, and
it reached the tablet as a 502, with no stretch and no count. What `heard` turns into an empty
string is the transcriber's `ValidationError`: an empty audio payload, a provider 4xx that is
not an outage, and an empty transcription — a recording with no words in it.

Decided: a telling whose transcription holds no words — empty, or only what the transcriber
wrote about the audio — is refused with 422 `WORDLESS_TELLING`, carrying `fixed_line`, the name
of the inaudible line the room says in its place, chosen as the finish route chooses it. It
creates no stretch and counts nothing: no retelling count, no hard stretch, no warning. A
provider 4xx is read as no words, as `heard` always read it. An outage stays a 502 the tablet
sends again. `heard` and its other callers are unchanged.

The retro take is stored before the transcription and stays stored: no recording is ever lost,
and the refused one is the team's work like any other.

ENG-706's counting of an empty retelling retires on this door only. The replace route's empty
re-recording still counts in place and is not touched here. The text seam used by golden runs
can still write a stretch from an empty transcript; it is not a door a team reaches and is out
of scope.

Rejected: turning the transcriber's `ValidationError` into a server failure on the chunk door.
The ticket's own case, a recording of silence, arrives as exactly that error, so it would have
become a 502 the tablet resends forever instead of the inaudible line.
