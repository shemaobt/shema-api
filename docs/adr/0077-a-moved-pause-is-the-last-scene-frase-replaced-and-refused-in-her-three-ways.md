---
status: accepted
date: 2026-10-20
---

# A moved pause is the last scene frase replaced, and refused in her three ways

The frase door of a **Scene rehearsal** took `replaces` on any frase of the attempt, with any
span, and walked a stale `replaces` to the chain's newest version. A team moving the pause of
one frase could therefore reshape any frase, from any version it had read, and the only refusal
it could meet was the overlap one, which the tablet reads as "read the list again" with no line
of hers to say why.

Decided (ENG-1349):

- A **Moved pause** is a frase posted through the existing frase door with `replaces`, whose
  span differs from the span of the frase it names. There is no new route (Henok, 2026-10-19);
  her own move-end goes through her segment door with `supersedes` too.
- It stands only when, in her order (her `moveEndVerdict`, `src/audio/moveEnd.ts` at 18fa7c4):
  1. the frase it names is still its chain's newest version, else `PAUSE_CANNOT_STAND_THERE`;
  2. that frase is the last current frase of the rehearsal's current attempt, the one with the
     greatest end and the later one on a tie, as the Ensaio Final reads "last", else
     `PAUSE_ONLY_ON_THE_LAST_FRASE`;
  3. it keeps the frase's start and is at least 200 ms long, the Ensaio Final's shortest frase,
     else `PAUSE_CANNOT_STAND_THERE`;
  4. its end is inside the scene recording when its length is known, with no slack because the
     door refuses every frase past it, else `PAUSE_PAST_THE_END`.
- The rule runs before the frase is stored and heard, and again under the rehearsal's lock after
  hearing, before the overlap refusal in both passes: a frase another tablet appended while a
  move was heard refuses the move with her line, not with a silent re-read. A move refused after
  hearing keeps its bytes and writes no frase, as a wordless frase does.
- The codes are the Ensaio Final's own moved-pause codes, answered 400 as there (the Definer,
  2026-10-19): one code per meaning on the wire, and the tablet already maps each to one of her
  three lines.
- A frase that replaces another over that frase's own place is the frase translated again, and
  keeps the chain walk to the newest version.

Considered:

- New codes named for the ticket (`PAUSE_NOT_LAST`, `PAUSE_PAST_END`, `FRASE_UPDATED`):
  withdrawn by the Definer, since they would be a second name on the wire for each of her three
  lines.
- A route of its own for the move: her move-end is the same door as a replacement, and a second
  door would need its own resend and lock story.

Consequences:

- An offline tablet's second move against a frase already replaced is refused, where it used to
  land at the chain's head. No client sent one before this change.
- A frase another tablet appends after a move landed, from the old end, is a new frase, so this
  rule does not see it; it overlaps the moved frase and the overlap refusal answers it, and that
  tablet reads the list again.
