---
status: accepted
date: 2026-10-23
---

# The team opens one Checagem externa per approved version, and nothing closes it

ENG-1421 asks that the team's one tap over an approved draft open the external check of that
**Version**, as Marcia's open does (app/api/external/open/route.ts at 18fa7c4). Decided: a team
door, `POST /sessions/{session_id}/external-check/open`, with no facilitator code. Over a draft
that stands approved (ADR 0071's `approved_draft`, ADR 0081), the first open of a version writes
one `ir_external_checks` row, unique per release row, keeping the version's parts (take id and
**Part key**) and frases copied from the release's stored packet (ADR 0014); every later open,
from any tablet of the team, answers that row. A draft that does not stand approved is refused
`DRAFT_NOT_APPROVED` (409), ENG-1274's code for the same fact, and nothing is written. The
creating open writes one `[checagem-externa] opened` server log line, and that is the only
notice. No route closes, locks or deletes a row; a Zerar stamps it with the passage's
**Archive** like every row hanging off a session (ADR 0047).

Rejected: answering the check from the release row alone, because ENG-1422 hangs listeners off
a record that must exist once per version and the open must be an act the room can tell
happened (her log line, the Desk's «aberta às»); a stored gate or `closed_at`, because of her
ruling of 4 September that the version does the work; re-deriving the frases on every read,
because comments stay pinned to what the listeners heard; keying the record on the packet's
`release_id`, because two teams of one mother tongue share that name (**Release**); a second
refusal code for this door; a Desk nudge on open, because the Desk reads nothing of the check
until ENG-1346 and learns of it on its next read.

Consequences: one row per approved version that a team opened, kept forever, and a new version
opens a new row while the older one stays as it was. A draft that re-opens stops answering at
the door until it is approved again. The copy never carries the team's words (`text`), since
listener work never meets a model. The listener rules are the app's ADR 0111.
