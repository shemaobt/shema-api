---
status: accepted
date: 2026-09-10
---

# A release is a numbered row, and a version is minted only when the packet changed

Until now the **Packet** was composed on demand, named by nothing, and its hash changed on
every read because the export clock sat inside the hashed content. Marcia's external check
hangs comments off a numbered draft ("v1, v2"), and a new version starts with zero listeners,
so the number has to exist and has to mean that something changed.

Decided: the team's approval writes a **Release** row, numbered per pericope per project one
past the last, under a unique index rather than a counter alone (the race ENG-639 recorded on
stretch positions applies here too). The index carries no predicate, unlike ADR 0006's pair:
those exclude superseded rows and a release is never superseded. Approving again returns the
existing release when the packet's hash is unchanged **against the last release of that
pericope and project**, and mints the next **Version** only when it differs — a packet that
comes back to an earlier version's content is a later draft, not that version again, and
handing its number back would put new comments on a draft nobody is reading. For
that to hold, the export clock leaves the hashed content first: the hash fingerprints the
release, not the read. A session without a project cannot be released, because a release is
named by project, pericope and version and the shared room key names no project.

Rejected: the content hash alone as the identity (nothing a team can hear or a comment can
point to), and a fresh version on every approval (a v2 with zero listeners for no change at
all). Consequence: the gate that decides *whether* a passage may be approved is a separate
decision (ENG-882); this row only records *that* it was.
