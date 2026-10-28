---
status: accepted; amends ADR 0081, and ADR 0019's rule that ADR 0014 holds under force
date: 2026-10-28
---

# A forced release is approved again once the telling is conferida

Only a change of takes re-opens a draft (ADR 0081), so an approval over the takes a release
already judged returned that release, forced or not. A passage the facilitator forced, whose
telling-back the team then checked clean, could never become a release nobody forced: its
check block came to read `conferida` but kept `forced` true, and the session read, the Desk and
the **Manifest** went on saying a person overruled a check the team passed. Marcia's approve gate offers «Aprovar como rascunho final» again exactly there,
and her finalize mints the next version, forced only when the gate was shut
(Tripod-Internalization `src/draft/approveGate.ts` and `app/api/draft/finalize/route.ts` at
18fa7c4; ENG-1837).

Decided: when the release a draft stands under is a **Forced release** and no **Blocker**
stands, an approval mints the next version instead of returning it. Her `conferida` is the
last check clean, every take heard, the same takes and nothing told since
(`src/backtranslation/store.ts` `passageStatus`), which is our gate with no blocker standing, so
the new version is an ordinary approval: not forced, `device_id` the tablet's, and its check
block `conferida`. The rule lives in `approve_release`, so the Desk's force over the same
passage mints the same ordinary version, as her finalize records a force over a conferida
passage as not forced (ADR 0080).

Unchanged: while any blocker stands, the forced release is returned to the team and to the
Desk as before, and a release nobody forced, or a force that waived nothing, is never minted
again over the same takes. The session read already says whether the current release was
forced (`approved.forced`), so no field and no migration are added.

Consequences: the new version starts its **Checagem externa** with no listeners, and the forced
one's stays readable by its version; a verdict written after the new version lands in its check
block, and the forced version keeps the block it last held. The tablet offers the button again
over a forced release in its own change.
