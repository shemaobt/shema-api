---
status: accepted
date: 2026-10-26
---

# The Analyst reads the translation only at «terminei»

The room used to read ahead: every told stretch stored through the chunks door or told again
through the replace door scheduled the **Analyst** in the background, over the whole passage,
once no piece of a divided stretch was left untold. The reading was stored on the session's
telling-back state as `read_ahead`, under the stretch ids it read. At «terminei», a stored
reading of exactly the stretches told, or one still running over them, was served instead of
asking the Analyst, so the check skipped one model call. Each stretch stored paid for one
reading, and a stretch told after it threw that reading away.

Marcia's app runs the Analyst only at «terminei» (`app/api/bt/check/route.ts` at 18fa7c4); its
stretch door (`app/api/bt/segment/route.ts`) stores and transcribes, and asks no model to read
the translation.

Decided (ENG-1208, from her app, per João's 26 Oct rule that her app settles business rules):

- Storing or retelling a stretch asks no model to read the translation. The Analyst reads only
  at «terminei» and in the text seam's round, which never read ahead.
- «terminei» always asks the Analyst over the stretches told; the call, its prompt and its
  inputs are unchanged. A row stored before this change may still carry a `read_ahead`; the
  state no longer has the field, so the row loads without it and the next save drops it. No
  migration: the state is a JSON column and its model ignores keys it does not name.

Rejected: keeping the read-ahead as a production choice. It never changed what the team saw or
heard, but it ran a model while the team translated, against her rule, and paid for a reading
on every stretch.

Consequences: the wait after «terminei» now always includes one Analyst call, which the
read-ahead had already paid when nothing was told after it. The Analyst's calls no longer reach
the session's `[llm-session]` total, since only the read-ahead ran under that ledger; each call
still writes its own `[llm-usage]` line.
