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
  span differs from the span of its chain's newest version. Measured against the newest
  version, not the version named, so a tablet that read the frase before a move cannot put the
  pause back by translating the old frase again over its old place. There is no new route (Henok, 2026-10-19);
  her own move-end goes through her segment door with `supersedes` too.
- It stands only when, in her order (her `moveEndVerdict`, `src/audio/moveEnd.ts` at 18fa7c4):
  1. the frase it names is still its chain's newest version, else `PAUSE_CANNOT_STAND_THERE`;
  2. that frase is the last standing frase of the attempt the move names, the one with the
     greatest end, set-aside frases counted, else `PAUSE_ONLY_ON_THE_LAST_FRASE`. A move whose
     restart has not landed yet is held and a move overtaken by a restart is set aside, as any
     frase of that attempt is (ADR 0059);
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
- A frase over the place of its chain's newest version is that frase translated again, and keeps
  the chain walk to the newest version. "Replaced since the tablet read it" is scoped to moving a
  pause: two translations over the same place at once both land, the later chained onto the
  earlier, and both stay as history, as ENG-1363 has it.

Considered:

- New codes named for the ticket (`PAUSE_NOT_LAST`, `PAUSE_PAST_END`, `FRASE_UPDATED`):
  withdrawn by the Definer, since they would be a second name on the wire for each of her three
  lines.
- A route of its own for the move: her move-end is the same door as a replacement, and a second
  door would need its own resend and lock story.

Consequences:

- An offline tablet's second move against a frase already replaced is refused, where it used to
  land at the chain's head, and so is a translation over the place a move left. No client sent
  either before this change.
- Measuring against the newest version holds while a request is heard, too: a plain
  translation of the last frase over its own place, heard while another tablet's move of that
  frase lands, is answered `PAUSE_CANNOT_STAND_THERE` under the lock, and that team hears «a
  pausa não pode ficar aí — a frase foi atualizada». That is right: its frase was moved under
  it, and keeping it would put the old pause back.
- A frase another tablet appends after a move landed, from the old end, is a new frase, so this
  rule does not see it; it overlaps the moved frase and the overlap refusal answers it, and that
  tablet reads the list again.
