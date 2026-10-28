---
status: accepted; extends ADR 0081
date: 2026-10-27
---

# The takes of a zeroed, unapproved re-opening download under the archive's stamp, never a version

ENG-1782. A draft re-opened after an approval, re-recorded and then zeroed by the Desk is no
draft and never reached an approval, yet its takes downloaded as `v<N+1>`, the name the next
session's first approval gives its own files. Two recordings could share a file name in the
consultant's downloads.

Decided: an archived session whose takes no longer stand on its own release downloads them as
`internalize-<tongue>-<passage>-zerada-<YYYYMMDD-HHMM>-<session language>-<part key>`, the stamp
being the archive's `archived_at` in UTC (Henok, 2026-10-24) and the session language the room's
(`pt`, `en`...). One Zerar stamps every language of the passage with one archive, and a passage
holds one session per language, so stamp and language name one session's takes. The same holds for a session archived before
any approval. An archived session whose takes still stand on its release keeps that release's name,
and nothing already downloaded is renamed.

All of the session's takes are renamed, the superseded ones included, as ADR 0081 already does.
The stamp is minute-resolution: two archives of one passage inside a minute would share it, and
the Zerar of a team's passage is a deliberate act that does not repeat that fast.
