---
status: accepted
date: 2026-10-19
---

# The tablet reads each told stretch's frase number from the room, not by counting

The voice says «na frase 3», and the pair screen of the check puts a numbered list beside it so
that 3 on the voice is 3 on the screen. The session read carried no number: a stretch was its
id and its slice. A tablet that counted for itself would number a stretch it had just told, and
appended before the next read, by where it landed in its own list — wrong whenever the team
tells out of sequence, and wrong again the moment a cut leaves two untold pieces that the voice
does not count.

Decided by the ticket (ENG-1679):

- `frase` is the stretch's 1-based position among the **told** stretches in the voice's order,
  that is `told_back(final_segments)`, the list the analyst is numbered off. It is null on a
  piece nobody has told yet, and that piece takes no number from the told ones around it.
- It is served on every `SegmentView` — the session read and the answers of a cut, a replacement
  and a restart — and on the telling answer, for the stretch just told. The number in the
  answer is the one the next read serves.
- One function gives it, `frase_numbers` in `services/internalization_room/back_translation.py`,
  beside `segments_block`, which writes the voice's lines. The packet and the retroverification
  file read it too. A test walks the application and fails on an `enumerate(…, start=1)` over a
  list named `told`, `segments` or `stretches`, or over `told_back(…)`, anywhere but there; a
  counter spelled another way is for review to catch.
- A stretch told again keeps its position, so it keeps its number. After «recomeçar a tradução»
  every stretch is retired and the next telling is frase 1.
- A finding's `frase` is the number the analyst gave and the voice spoke, followed to where the
  stretch it named stands now (ENG-1681). The stretch is the one at that position in the list
  the analyst was shown, `analysed_segment_ids`, and its number is read off the told stretches
  as the session read does; it is null once that stretch is not among them. A missing element
  placed after frase N says N while its `segment_id` is the stretch after it; reading the
  number off the pointer would say N+1. The stored `chunk` is untouched: the packet hashes it
  and a Swap is paired on it.

No migration: the number is derived at read time from the stretches that stand. No model call.

Consequences:

- Every number the session read and the check's answer serve is true of the reading as it
  stands now. The text seam, the packet and the retroverification file still carry a finding's
  `chunk` as the check made it.
- The telling answer carries no count of stretches (see the amendment below), so the one number
  it gives about where the stretch sits is its `frase`.
- The tablet and the Desk parse the session by named keys and ignore the rest, so the new key
  breaks neither.

Rejected:

- Counting on the tablet: it cannot know which pieces the voice leaves out, and it numbers a
  stretch appended before the next read by guesswork.
- A number stored on the stretch's row: every cut, replacement and part recorded again would
  have to renumber the rows after it, and the packet already freezes the number per **Version**
  for the reason that a stored one moves.

**Amended on 20 October 2026 (ENG-1682): the telling answer no longer counts stretches.** The
answer carried a `chunks` number documented as how many stretches the passage has, and it was
every stretch that counts, told or not: with an untold piece standing it differed from the
highest `frase`, and a stretch told again left it where it was. Nothing read it. The tablet
parsed it into a field no code looks at, the Desk and the golden runners never touch the route,
and the number is not one the voice speaks, so there was no reading of it worth keeping true.
The field is gone from the answer and from the API reference. The tablet reads
`json['chunks'] as int? ?? 0`, so an answer without it and a replayed answer that still has it
(the room replays a stored answer byte for byte for a day) are both read.
