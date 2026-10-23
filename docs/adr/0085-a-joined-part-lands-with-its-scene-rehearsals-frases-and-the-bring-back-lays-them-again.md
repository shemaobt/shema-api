---
status: accepted
date: 2026-10-23
---

# A joined part lands with its scene rehearsal's frases, and the bring-back lays them again

A joined part is a scene rehearsal laid in byte for byte, and the team already translated that
rehearsal frase by frase. Until now the part landed with no stretch, so a joined recording had
to be translated twice. In her app the join carries the frases over, and «trazer de volta as
traduções do ensaio desta cena» brings them back after a restart (`src/draft/join.ts`,
`app/lib/ensaioFinal.ts:587-634` at her freeze 18fa7c4).

Decided (ENG-1405):

- **Laid on landing.** A part that lands with `origin` gets its rehearsal's current frases as
  told stretches, in place order, one per frase, each with the frase's place, words and telling.
  A replaced frase and one set aside by a scene Restart are not laid, nor is a frase shorter
  than a stretch can be (200 ms): its ground stays untold, and the frase stays in the rehearsal
  (Orchestrator, 2026-10-23). The lay happens only when
  the part is a current part, the rehearsal is of this session, the part's bytes are the
  rehearsal's, and no stretch row was ever written on the part, current or retired. Ground the
  frases leave uncovered stays untold, and the listen names it N-3 as before (ADR 0070).
- **A resend lays nothing new.** The same join sent again answers the take already kept. It
  lays only if nothing was ever written on the part, which heals a lay that never committed.
  So a restart is never undone silently.
- **The Bring-back** (`POST /sessions/{id}/parts/{n}/bring-back`) is offered, as
  `back_translation.bring_back` on the Session read, for a current joined part whose rehearsal
  is of this session, whose bytes are the rehearsal's, whose rehearsal has a current frase, and
  on which no current stretch sits at a frase's place with its words. It abandons the part's
  current stretches and their pieces, keeps them as history, lays the frases, drops the
  findings and nuances on the abandoned stretches as recording a part again does, and undoes
  the check as any capture does. A part whose frases already stand answers as it is. Anything else
  answers 409 `NOTHING_TO_BRING_BACK` with nothing written, and a number with no part 404.
- **The telling is a `retro` take row naming the frase's stored object**: the same key,
  fingerprint, checksum, size, type and verification; its Recording time is the frase's arrival;
  one row per frase in the session. The lay is database writes only, in one transaction.
- **The lock is the part's `ir_takes` row**, taken before the checks, which are read again under
  it. The telling-back state is written through `save_back_translation`'s compare-and-set.
- **Stretches waiting to be told again on the part's earlier takes stop waiting** once frases
  are laid on it. They stay retired, as history.
- **ADR 0072's two bullets on a joined part are amended** (Definer Q67). A joined part's
  Recording time is the tablet's `recorded_at` as for any take (none sent → its arrival): the
  moment the team chose it, raw, on the tablet's clock. The **Clock offset** is read from a new
  form field, `sent_at`, the tablet's clock as it built that send, so it measures a clock and not
  a queue's delay. Five minutes or more is still one line for the consultant alone.

Rejected: **copying the frases' audio through the store**, because it puts bucket reads and
writes inside two doors and lets a part land without its frases; **a stored mark on laid
stretches**, a migration, where the place and the words already tell; **the session row lock**,
which ENG-1754 keeps to one writer; **laying on every resend**, which would undo a restart
without anybody asking; **laying another language session's frases**, because they would sit
under a check in another language (Definer Q46); **a `DRAFT_APPROVED` guard on the Bring-back**,
which has its own armed text, as the Restart does; **the server's arrival as a joined part's
Recording time**, because the join and the hand take would then be ordered on two clocks (Q67).

Consequences: ENG-1407's swap lands through the same lay. Over an approved draft a Bring-back, like the Restart, makes the draft no longer
the approved one (ADR 0071). A team that corrected every laid frase one by one is offered the
Bring-back again; taking it keeps their corrections as history. The laid tellings are `retro`
takes, so the tablet's takes list, the packet's `retro_takes` and Refine's downloads carry them
under the frase's own audio. A sentence laid into a part between the Bring-back's checks and its
writes holds the session row while the Bring-back holds the part's: both are one team's taps on
one part, and the race is left open rather than widening either lock. So is a lay racing a hand
recording of the same number: the retire of the hand take reads no stretch the uncommitted lay
wrote.
