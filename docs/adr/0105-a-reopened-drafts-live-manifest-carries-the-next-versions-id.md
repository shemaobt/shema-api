---
status: accepted; supersedes the live draft's id in ADR 0086
date: 2026-11-03
---

# A re-opened draft's live manifest carries the next version's id

ENG-2142. After a re-open the take downloads, the whole-passage file and the retroverificação
file named the draft as the next version (ADR 0081), while the live manifest named it after the
passage's last release. One Desk row, two names for one draft.

Decided (Henok, 3 November): a draft that is not approved as it stands is the next version's
draft, `v(N+1)`, version 1 when the passage has none, and the live manifest carries that id as
every other download does. An approved draft that stands keeps its version's id, and a session a
Zerar archived keeps ADR 0100's naming. `finalizeCount` stays the last version.

Rejected: the last version's id everywhere, which is what Marcia's own route does; it would rename
the take downloads and amend ADR 0081.

Consequence: the manifest of a re-opened draft no longer matches her route's `releaseId`. Refine
matches clips by `takeId` and `sha256`, never by file name (ADR 0073).
