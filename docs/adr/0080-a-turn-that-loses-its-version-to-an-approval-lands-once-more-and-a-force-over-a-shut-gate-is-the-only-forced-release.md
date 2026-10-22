---
status: accepted
date: 2026-10-22
---

# A turn that loses its version to an approval lands once more, and a force over a shut gate is the only forced release

An approval claims the session's version so that a Zerar or a turn that moved the session first
refuses the mint (ADR 0052, ADR 0066). The claim writes nothing in the conversation, yet a team
turn whose Guide was still answering when it landed lost `_land`'s version guard and answered a
generic 409, and the Guide's paid line was lost with it. The tablet does not ask a turn's 409
again. Separately, a force over a passage with nothing to waive was recorded as forced, on
purpose: the row said who pressed the button. Her finalize (Tripod-Internalization
`app/api/draft/finalize/route.ts` at 18fa7c4, lines 58-70) records a force as forced only when
the translation is not conferida, and the ticket's acceptance 8 asks for her rule (ENG-1259).

Decided by the Definer on 2026-10-22 (recorded on ENG-1259):

- A team turn whose guarded write matches nothing reads the row as stored now. When the
  session is still live and the conversation it read is still the conversation stored,
  whatever moved the version moved nothing the turn writes over, and the turn lands once more
  on the stored version. When a Zerar archived the session it is answered as gone (ADR 0052);
  when the conversation moved, or the second write also matches nothing, it is refused as
  before. The archive and the conversation are read in one statement, so a Zerar that lands
  between the first write and that read is never taken for an approval.
  One more write at most. Only a turn takes the second landing: an approval that loses its
  version to a turn is still refused (ADR 0066). The Turn claim is untouched (ADR 0079): it
  orders turns among themselves, and the approval does not take it.
- A force that waives no blocker is an ordinary approval: `forced_by`, `forced_at`,
  `forced_blockers` and `forced_open_findings` are null, and the check block's `forced` is false
  with `forcedBy`, `forcedAt` and `forcedBlockers` null. A force that waives any blocker stays
  forced, including ADR 0075's clean check with a part not heard, which still reads `conferida`
  with `forced` true and the listening among the blockers passed.

Rejected:

- The approval takes the Turn claim. It would wait up to 90 s behind a Guide, and a turn already
  past its claim would still lose the version.
- The approval does not move the version. A Zerar, or a session that moved, would no longer
  refuse the mint (ADR 0052, ADR 0066).
- Any lost landing is retried. A turn that lost to another turn would write over that turn's
  exchange, which is what `_land` exists to prevent (ENG-643).
- The 409 is kept and the tablet asks again. The Guide's line is already paid for and lost, and
  the tablet does not ask a turn's 409 again.
- A clean force stays forced (the rule before this one). A clean passage would read as forced in
  the manifest, the dossier and the retroverification file, which is the record the ticket says
  misleads the consultant.

Consequences:

- A turn lands after an approval that was minted from the conversation before it. The packet
  reads nothing from the conversation, so the approved draft stays approved and asking again
  returns the same release.
- Any other write that leaves the conversation as it was, not only an approval, is landed over
  once in the same way; the turn writes only its conversation and the team's return, so it
  carries over nothing that write changed.
- A clean force no longer records who pressed it. The Desk already draws a null `forced_at` as a
  release nobody forced.
