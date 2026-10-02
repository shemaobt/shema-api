---
status: accepted
date: 2026-10-02
---

# The Golden doors speak her runner's wire and read the runner key as a bearer credential

Marcia accepts the product by playing her golden scripts through her own runner against a
server: `POST /golden/session` opens a session, `POST /golden/turn` plays a turn, each with her
field names, and her runner sends `Authorization: Bearer <token>`. Our text seam took other
names on other paths with `X-Access-Code`, so her runner could not play a single script
against us. ENG-1331 makes our doors hers. Her runner, our `scripts/golden_runner.py` and the
slices João and Jonatas test with all depend on this wire, so changing it again breaks every
one of them at once.

Decided by the Definer under Henok's standing rule on 2026-10-02 (Q21–Q28 on ENG-1331):

- The seam's conversation doors are renamed to `/golden/session` and `/golden/turn`, with her
  request and response, read from her `src/golden/httpDriver.ts` at 18fa7c4. There is no
  second door: our runner moves to her names, and so no longer plays her own app, whose
  routes are not these.
- The Golden doors read the runner key as a bearer credential; the back-translation seam keeps
  `X-Access-Code`. One rule decides both: no key configured answers 404, a missing or wrong
  key 401.
- A request key the doors do not know is ignored, never refused. Her runner adds fields over
  time, and a strict validator kills her run before its first turn.
- Every field she sends is read. Her `noteText` is the one read only to be set aside: the room
  renders its own notes. On every turn the response's `transcript` is exactly what the Guide
  was handed in the team's place — on the opening, the room's own opening instruction — so her
  judge reads what our Guide read (Q31).
- A `teamText` that is present, even empty, is a team turn, and one with no words goes the way
  the tablet's does, to the inaudible ladder. Only a turn with neither words nor a room note
  is refused.
- The interruption is a room note, like the mother-tongue one: the Guide is handed the note
  in front of the words, the conversation keeps the note as the room's and the words as the
  team's, and only the team's words are ever settled.
- The mother-tongue note is her full text, and it is the one note the room has, so the
  tablet's turn speaks it too. Its seconds are said as her note says a number; a take the
  tablet measured is rounded to the second where it is measured.
- Earlier passages are stored on the session, never in its messages, because a session with
  messages has already spoken and refuses the opening. They reach the Guide as her fact line,
  beside the coverage block, complete or not at all, as her app renders it.
- Scene rehearsals are refused when they name a scene the passage lacks, and are kept on the
  turn's Guide entry, the one entry every turn has. What a rehearsal does is ENG-1357's.
