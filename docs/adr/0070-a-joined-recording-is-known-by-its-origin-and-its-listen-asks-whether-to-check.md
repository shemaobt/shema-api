---
status: accepted; amended by ADR 0074: the listen door is where the tablet reports, and every answer names the parts still unheard; extended by ADR 0085
date: 2026-10-19
---

# A joined recording is known by its origin, and its listen asks whether to check

Her join lays each scene rehearsal into the passage recording as a clip stamped with where it
came from, and that stamp is what makes a recording joined (`bt/check/route.ts:13` at her
freeze 18fa7c4). On one, a scene with no translated frase refuses every check, a stretch of half
a second or more nobody translated refuses only the check the app runs by itself
(`untranslated.ts:15-65`), and after the first full listen of one translated through the voice
says N-2 and the verdict follows with no tap (`ensaioFinal.ts:431-455`). The server had no fact
that could tell a joined recording from any other.

Decided, as hers (ENG-1207):

- A take upload may carry `origin`, the id of the team's live scene rehearsal of the passage the
  part was laid in from, kept on `ir_takes.origin`. An id naming no such rehearsal is refused
  422. A recording is joined when any current part carries one.
- *Terminei* on a joined recording refuses `STRETCH_UNTRANSLATED` for a part no translated frase
  stands on, after `PART_UNHEARD` and before `NOTHING_TRANSLATED`, naming each part on
  `untranslated` with its scene number and `from_ms`, and her N-3 by position (`N2`). The team's
  tap is their word that nothing was said elsewhere, so a stretch on a part with frases never
  refuses it.
- `POST /back-translation/listened-whole` takes the finish's own playback report and answers in
  her order: a frase awaiting, a part unheard, a recording no join touched or one that carried
  no translation say nothing; a part with no frase or a WAV part's stretch of 500 ms or more is
  `STRETCH_UNTRANSLATED` with N-3; a record already holding a check stays quiet; otherwise
  `automatic_check` with N-2 by position (`N1`). A part's length is the one the tablet measured
  playing it, and only a WAV part's is trusted, as hers trusts only a WAV clip's.
- The door decides and checks nothing. The tablet says N-2 and calls the finish, so the check
  has one implementation and the Observation Room sees each round as it sees a tapped one.

Rejected: **a door that runs the check**, because it would answer N-2, «Um momento», only after
the half minute it announces, where hers says it first; **a duration column on the take**,
because the length the listening rule already trusts is reported with every listen;
**`PROCESS_STEPS` for the N family**, because her N block holds a line she keeps unspoken that a
step would let through.
