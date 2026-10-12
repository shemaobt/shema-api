---
status: accepted
date: 2026-10-08
---

# The consultant is a platform role that reads every team and writes nothing

Marcia's observation room is a second page behind the one facilitator code: whoever holds the
code reads every session of the deployment and can also reply, force and Zerar from the other
page. Her texts still name the consultant as the one who reads what the team no longer sees,
«só para o consultor», and the PRD (chapter 21) leaves to production whether there is one room
or two and whether the consultant gets an identity of his own. Our Desk admits a person by a
personal sign-in, the `facilitator` role on the internalization-room app and a facilitator link
on each team, and the only reader of every team is the platform admin, who also writes.

Decided by Jonatas with the Definer on 2026-10-08 (ENG-1213):

- The consultant is a role `consultant` on the app `internalization-room`, granted to a person
  like `facilitator` is, never a link to a team. Holding it reads every team; nothing about it
  writes. A person can hold both roles and acts only on the teams they facilitate.
- Every facilitator read door admits `facilitator` or `consultant`, with the consultant's scope
  being every team; every write door keeps the `facilitator` gate and the per-team link. The
  audits that walk the facilitator routes prove both sides.
- One room, two views by role. The Desk keeps one address and one set of pages; a team the
  reader does not facilitate shows the record and none of the controls. The facilitator gains
  the record the consultant reads; the consultant loses nothing.

Rejected:

- A per-team consultant link. Every new team would need a grant, and "every team" is the point
  of the role.
- The platform admin as the consultant. The admin writes everything, against the one rule the
  room has: reading changes nothing.
- A separate read-only room. A second UI repeating the Desk's pages, with the facilitator left
  without the record; the frozen app's split is one of layout, not of permission.
