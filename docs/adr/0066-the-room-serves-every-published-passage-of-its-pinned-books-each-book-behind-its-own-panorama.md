---
status: accepted
date: 2026-10-18
---

# The room serves every published passage of its pinned books, each book behind its own Panorama

Her app at 18fa7c4 offers all 37 passages of the pin 5b5c8d2 (Esther, Jonah and Ruth) with no
gate: `listPericopes` lists every map, sorted by id, and each book opens with its own Panorama.
The room served Ruth alone, and three tests held passages back: no preservation rule (ENG-589),
a checklist that disagreed with the survey, and a missing spoken line. Parsing also refused a
map whose genre was not narrative or whose status was not complete, which took all of Jonah
down with its poem (J03).

Decided by the ticket's rule (ENG-1248) and the Definer's order of 2026-10-18:

- The **Served books** are her published books at the pin. Every map of a served book is
  offered and opens; the only refusal left is a book the room does not serve.
- Each book's list starts with its Panorama entry under the id the open door takes,
  `OV-<Book>`. `OV` and `panorama` stay Ruth's, for tablets that name no book. A Panorama of a
  book the room does not serve is refused at the open, before anything is written.
- An entry with no written spoken line, or whose line the synthesiser cannot voice, is offered
  with no sound (`audio_url: null`); the list is never failed for it.
- A map is read whatever its genre or status.
- A passage's book is the book of its map, never a default.
- No release is minted on an archived session: the approval is refused when the session is
  archived, and its insert lands only while the session's version is the one it read.

Consequences:

- Esther and Jonah walk with no preserved bead; their Panoramas read «- (none recorded)», and
  the Validator gets no rule there. Their beads are named from the canon, since they have no
  label catalogue.
- The passages door's wire changes: the Panorama id, and `audio_url` may be null. The tablet
  reads both.

Rejected:

- Her 31 August gate (shema-api #732), because the ticket's rule decides.
- A book column on releases: a passage id is already book-qualified (E01, J01, P01).
