---
status: accepted
date: 2026-10-14
---

# A scene rehearsal is sent once, claimed on its row under a turn id

«terminei» sends a **Scene rehearsal** to the voice as a **Rehearsal turn**. The tablet sends
the rehearsal by reference, with a turn id it minted. The server builds the team's side of the
turn from the stored record. Two tablets of one team can press «terminei» on the same rehearsal.
A frase can also land during the seconds the Guide takes to answer. Her app marks the rehearsal
sent after the turn is saved, best effort, so both tablets could reach the voice. A frase that
landed meanwhile was kept, but it was missing from the text the voice heard. ENG-1321 brings the
send to the server.

Decided by the Definer on 2026-10-14 (recon wave 2, and the wire rule after review, both
recorded on ENG-1321), with the row settled in the plan:

- The send is claimed before the voice is asked. The Definer's words name the session's row.
  The claim sits on the rehearsal's own row instead, because that is the lock a frase and a
  restart take: a claim on the session's row would never meet them. The claim stamps
  `sent_at` and `sent_turn_id` under that lock, with a conditional `UPDATE … WHERE` on the
  stamp it read, so it holds on SQLite too, where the lock does nothing. The live frases are
  read under the same lock, and the claim commits on its own. A frase that arrives after the
  claim is refused as `SCENE_REHEARSAL_SENT`, the refusal ADR 0059 gives a sent rehearsal. It
  is never kept while missing from the sent text.
- The send names the attempt it closes, the uuid its frases carry, and none before any
  restart. It is refused with 409 `RESTART_OUT_OF_ORDER` when that attempt is not the current
  one, or while a frase waits on a restart still on its way. The outbox retries it once the
  restart lands, as it retries a restart that overtook its predecessor (ADR 0059), so a send
  never freezes an attempt the team had already left.
- Another turn id meets a standing claim. It is refused with 409 `SCENE_REHEARSAL_SENT` only
  once a turn has landed under the claim's turn id. While the claim is live and nothing has
  landed, it is refused with 409 `SCENE_REHEARSAL_SENDING`, which the outbox retries: that turn
  may still fail and leave the rehearsal sendable.
- A claim older than an opening claim may live, the turn bound plus thirty seconds (ADR 0053),
  with no turn landed under its turn id, belongs to a request the deployment has already
  killed. It counts as no claim, and a new turn id takes it over.
- A resend under the same turn id is answered from the stored answer before anything else
  (ADR 0043). It joins an answer still in flight in this process. Otherwise it renews the claim
  with a fresh stamp and drafts again from the live frases, which the claim froze.
- A turn that never lands, because the bound passed or the draft raised, releases the claim.
  The release clears only the claim this request made: the stamp it wrote and its turn id, as
  ADR 0053 guards an opening claim's release. A resend that renewed the claim holds it, and a
  turn stored under the turn id keeps the rehearsal sent, whichever request failed after it. A
  Guide that fails answers with a fail-safe line. That is a landed turn, and the rehearsal
  stays sent.
- A rehearsal with no live frase is refused with a plain 422 and stays unsent.

## Consequences

- `sent_turn_id` names the turn whose reply answered the rehearsal. The Guide's entry of that
  turn keeps which rehearsal it was, how many frases it had, the recording's length, the
  session's language and the scene label as it stood at sending.
- `sent_at` is the stamp of the claim that stands, so a renewed claim moves it. Once a turn has
  landed, it is when the rehearsal was sent.
- The same turn id resent to another instance while the first draft runs still drafts twice,
  as the turns door does: `answer_once` joins only within one process.
