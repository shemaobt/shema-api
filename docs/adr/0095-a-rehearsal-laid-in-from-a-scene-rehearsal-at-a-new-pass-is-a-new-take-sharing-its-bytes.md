---
status: accepted
date: 2026-10-23
---

# A rehearsal laid in from a scene rehearsal at a new pass is a new take, sharing its bytes

The **Rehearsal swap** (ENG-1407) lays a scene rehearsal in as a part's next pass. Swapping back
to an earlier rehearsal sends bytes the session already holds. Until now the take door answered
any keep of known bytes with the row that held them, whatever its number and pass, so A → B → A
landed as nothing: the room kept B as the part while the tablet believed A was. The same check
answered a rehearsal joined under another part with that other part's take. Her server names a
joined take by its bytes and the take it is laid over, and keeps the same bytes over a different
take as a new one (`src/draft/join.ts:225-240` at 18fa7c4).

Decided (the Definer, 2026-10-23, Q38):

- A take laid in from a scene rehearsal (one carrying `origin`) is the part standing under its
  number when that part is already this rehearsal, with the same bytes, whatever pass the tablet
  counted: a second tablet joins above the pass it last listed, and must land on the one part
  (the Orchestrator, 2026-10-23, from ENG-1385's acceptance 7). Otherwise it is the same take
  only under the same bytes, part number and pass: a resend from the Outbox, including a late
  one of a rehearsal the team swapped away from, which never takes the part back. Otherwise it
  is a new row. A → B → A is three takes, and the last is the part.
- A take recorded as itself is still its bytes, once per session, and never answers a joined row.
- The joined rows of the same bytes share one stored object: the storage key stays the bytes'
  hash.
- ADR 0081's guard asks the same question, so a swap back over an approved draft takes the armed
  tap, and a resend of a join that already landed is never refused.
- One migration replaces the two uniqueness rules on `ir_takes` with three partial unique
  indexes: the key and the bytes once per session among takes recorded as themselves, and the
  bytes, number and pass once per session among joined takes. The last is the race guard for
  two tablets sending the same join at once. A take a **Grain switch** set aside stays outside
  all three, as ADR 0096 put it outside the two before. It is reversible until the first swap back: over a
  session holding two takes of the same bytes the old index fails loudly on the way down, and no
  take is deleted.

Considered and rejected:

- Re-stamping the old row's **Recording time** on a swap back: a take's time is never moved once
  stored (ADR 0072, ADR 0090).
- Copying the object under a pass-suffixed key: doubles the bytes for nothing, and the
  content-addressed key is what makes a resend safe.
- Keying the joined identity on bytes and number alone: A → B → A → B would collapse two swaps.

Consequences: two rows can share one stored object, and nothing in the room deletes take
objects. The Desk's downloads list each row. A joined take sent with no number or no pass is the
same take as an earlier one sent the same way, and the race guard reads a missing number or pass
as one value, so two such deliveries at once still leave one row.
Two tablets joining the same rehearsal at different passes at the same instant both miss the
standing part and leave two rows of the same bytes under that number; the newer is the part and
both hold the same audio. No index can say which take is standing.
