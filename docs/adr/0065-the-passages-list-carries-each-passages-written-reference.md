---
status: accepted
date: 2026-10-16
---

# The passages list carries each passage's written reference

The passages list (`GET /books/{book}/passages`) said on purpose that it had no text: the team
did not read, so a passage was told apart by its spoken line. ENG-1297 gives the facilitator's
tablet a text menu, whose pill is the passage's Scripture reference. The tablet has no other
source for it.

Decided by the Definer on 2026-10-16 (ENG-1297):

- Each passage entry carries `reference`, the **Meaning Map**'s heading reference exactly as it
  is written (`Ruth 1:1–5`, `Ruth 2:8-16`), read from the deployed canon, as the list already
  reads its beads. The Panorama carries none (`null`).
- The tablet renames the book in the room language itself. The server does not translate it.
- A scripture reference is not a team word. The spoken line stays: the list still offers only
  the passages the room can say.
