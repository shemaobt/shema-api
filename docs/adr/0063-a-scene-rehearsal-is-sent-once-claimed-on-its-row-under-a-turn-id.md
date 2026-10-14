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

Decided by the Definer on 2026-10-14 (recon wave 2, recorded on ENG-1321), with the row
settled in the plan:

- The send is claimed before the voice is asked. The Definer's words name the session's row.
  The claim sits on the rehearsal's own row instead, because that is the lock a frase and a
  restart take: a claim on the session's row would never meet them. The claim stamps
  `sent_at` and `sent_turn_id` under that lock. The stamp is a conditional
  `UPDATE … WHERE sent_at IS NULL`, so it holds on SQLite too, where the lock does nothing. The live frases are read under the same lock, and the claim commits on its
  own. A frase that arrives after the claim is refused as `SCENE_REHEARSAL_SENT`, the refusal
  ADR 0059 gives a sent rehearsal. It is never kept while missing from the sent text.
- A resend under the same turn id is answered from the stored answer before anything else
  (ADR 0043). It joins an answer still in flight in this process. If neither exists, because
  the process died mid-draft, it drafts again from the frases its own claim froze. Any other
  turn id on a sent rehearsal is refused with 409.
- A turn that never lands, because the bound passed or the draft raised, releases the claim.
  The release is guarded on the claim's own turn id, as ADR 0053 releases an opening claim, so
  the rehearsal can be sent again. It is guarded too on no turn stored under that id: a resend
  of the same turn id that drafted again on another instance and failed after the first draft
  landed leaves the rehearsal sent. A Guide that fails answers with a fail-safe line. That is a
  landed turn, and the rehearsal stays sent.
- A rehearsal with no live frase is refused with a plain 422 and stays unsent.
- Unlike an opening claim, a send claim never goes stale. A rehearsal whose process died
  mid-draft can be sent again only under the turn id that claimed it. That is the id the
  tablet's outbox resends.

## Consequences

- `sent_turn_id` names the turn whose reply answered the rehearsal. The Guide's entry of that
  turn keeps which rehearsal it was, how many frases it had, the recording's length and the
  scene label as it stood at sending.
- A tablet that drops a turn id it has not yet heard an answer for leaves the rehearsal frozen
  with no reply. Only that turn id can bring the reply back.
