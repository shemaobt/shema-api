---
status: accepted
date: 2026-10-22
---

# A team's progression is per served book, and it stands in the book of its latest session

ADR 0066 serves Esther, Jonah and Ruth whole, but where a team stands was still Ruth's. A team
that closed Ruth read COMPLETE on the Desk with Esther and Jonah untouched. An open that named
no passage and followed no session landed in Ruth, and a team done with Ruth got a 409 there.

Decided by the ticket's rule (ENG-1709) and the Definer's answers of 2026-10-22:

- Progression and standing are computed per **Served book** from the session rows. Passage ids
  are already qualified by book (E01, J01, P01), so nothing is stored and no migration is run.
- A team stands in one book, its **Current book**. It is the book of the team's latest live
  session, a Panorama included, in the order the Desk reads a team's sessions (a room the team
  entered first, then the most recent), while that book still has an unclosed passage.
  Otherwise it is the first of Ruth, Esther and Jonah that has one. A session whose pericope
  no served book holds is passed over.
- When the book a team is in is done, the server moves the team to the first of Ruth, Esther
  and Jonah that has a passage left, whichever book it was in. So a team that closed Ruth and
  opened nothing else is in Esther, on E01.
- A facilitator's visit is not the team's act and does not move it: marking a room attended,
  or undoing the mark, leaves the session's `updated_at` as it was, as the other writes that
  are not the team's already do.
- There is one current passage per team, in its Current book. Every unclosed passage of any
  other book is future.
- A team is COMPLETE only when every passage of every served book is closed. Complete means
  closed, not approved.
- An open that names no passage lands in the Current book. An open that follows a session
  still lands in that session's book.
- `/pericopes` keeps its shape and answers the Current book's passages. The team detail's
  `active_passage`, `closed_total` and `approved_total` describe the same book, because the
  Desk refuses to draw when they disagree.
- The team detail gains `books`, one entry per served book in the order of GET /books: its
  passage total, its approved count and whether it is complete. The queue's row does not get
  it, because it is a fact about one team.

Consequences:

- A team that closed Ruth and stopped is `in_progress`, not COMPLETE. After 21 quiet days it
  reads «Inativa» where it used to read «Concluída».
- Stored sessions are read as they are.
- The work queue costs one more statement, and the team detail one more.

Rejected:

- `/pericopes` answering every served book. The Desk titles the list by its first row and
  draws «N de <length>», so it would read «Ester» and «N de 37».
- A current passage in every book. A team is in one place, and the Desk opens on its one
  active passage.
- A stored current-book column. The ticket asks for no migration, and every position here is
  derived.
- Keeping a team in a done book with no active passage until it opens another. The Desk would
  have no passage to open on, and an open with no passage would answer 409 to a team with work
  left.
- Approved as the meaning of complete. The glossary keeps the two apart.
