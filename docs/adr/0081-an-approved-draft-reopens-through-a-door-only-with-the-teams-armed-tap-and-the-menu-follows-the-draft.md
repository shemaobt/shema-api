---
status: accepted; extends ADR 0071, amends ADR 0078
date: 2026-10-23
---

# An approved draft re-opens through a door only with the team's armed tap, and the menu follows the draft

ENG-1260 asks that a change over an approved draft take the team's **Armed tap**, as Marcia's
join and splice refuse a finalized draft without `reopen` (join.ts:204, splice.ts:157 at
18fa7c4). Decided: over a draft that stands approved (ADR 0071's `approved_draft`), the keep
door refuses `DRAFT_APPROVED` (409) a join or swap that would put a new take in place and a
whole take over a joined recording, and the sentence door refuses a re-recorded sentence,
unless the request carries `reopens_the_approved_draft`. Nothing is stored. A take already
kept brings nothing new and is never refused, and a part recorded on the recording screen
takes one tap and re-opens the draft, as hers does.

Only a change of takes re-opens a draft (Marcia, 1 October; ENG-1256's acceptances 1 and 2,
the Definer's answers of 23 October): a draft is one session's rehearsal takes by
fingerprint in their order. A telling told again, a stretch divided, a verdict, a question
answered, the nuances, the listening and the Restart are the approved version's check state
and leave it approved. This amends ADR 0078, which compared the whole content.

The book wheel's and the Desk's `approved` mean that the draft stands under the passage's
latest live release, not that a release exists, so a re-open clears «●» on every tablet on
its next read while the release stays in the history. The session read's `approved` gains
`listeners`, none until ENG-1422 keeps them.

Rejected: a stored `reopened_at` on the release, because ADR 0071 derives approval on every
read and a stored mark misses the changes that re-open with no door; refusing every keep
over an approved draft, because her recording-screen take has no `finalized` check
(route.ts:90-118); refusing in the sentence route before the splice, because the door asks
twice (ADR 0089) and a draft approved during the bucket write would slip past; keeping the
wheel on "a release exists", because her menu reads `finalizedAt`, which a re-open clears.

Consequences: the wheel and the Desk compose one packet per passage with a release. The
Desk's count of approved passages drops when a team re-opens. An approval racing a keep (the
release minted between the keep's check and its row) lands the take without the flag: the
storage primitive knows nothing of drafts, and the window is the bucket write. The Guide's
earlier-passages fact still reads "has a release". A whole take over numbered parts is kept
but set aside until the grain door (ENG-1765) makes it the draft.
