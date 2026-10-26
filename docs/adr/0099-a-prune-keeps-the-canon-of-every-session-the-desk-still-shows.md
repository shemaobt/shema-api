---
status: accepted
date: 2026-10-26
---

# A prune keeps the canon of every session the Desk still shows

Amends ADR 0088, which accepted that a session archived by a Zerar may lose its canon at the
next prune. The Desk still reads such a session by its id: its coverage and its release answered
409 `CANON_NOT_KEPT` once the tree was gone, and the questions page lost its labels. Zerar
moves nothing and deletes nothing («zerado só para a equipe», ADR 0047), and ADR 0052 keeps the
facilitator's by-id doors unfiltered, so a canon that leaves under an archived session leaves
under a session the consultant still opens. Decided for ENG-1626, form (b): the sync keeps
kept trees until a person prunes them.

Decided:

- The `canon-pins` read names the pin of every session, archived ones included. A prune keeps
  a kept tree while any session names its pin, the pin production serves or the deployed pin.

Consequences:

- A kept tree leaves only when no session at all names its pin, so kept trees build up for as
  long as their sessions are stored.
- An archived pin with no kept tree makes the prune refuse, as a live one does: a checkout
  behind production.
