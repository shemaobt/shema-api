---
status: accepted
date: 2026-10-20
---

# A part is heard under her rule, one rule for a part and a stretch, and listening reports add up per take

A part counted as heard when no single gap in what was played exceeded 750 ms and the reach
landed within 750 ms of its end (ADR 0017's covering sentence). Eight holes of 0.7 s, 5.6 s
nobody heard, passed; so did a one-second part with 0.3 s played. A sentence laid into a part
(ADR 0069) was measured by a second rule, which summed but never joined. And the stored report
was replaced by each new one, so a report naming fewer parts erased the listening to the others.

Hers, at her freeze 18fa7c4:

- `src/backtranslation/heard.ts:22-38`: `HEARD_TOLERANCE_SEC = 0.75`, the slack is
  `Math.min(HEARD_TOLERANCE_SEC, durationSec / 2)`, and a clip is heard when
  `durationSec - covered` is within it; "an ABSOLUTE tolerance ..., never a percentage".
- `app/lib/chainPlayer.ts:50-60` and `src/backtranslation/store.ts` `mergeRanges`:
  `if (last && s <= last[1] + 0.25) last[1] = Math.max(last[1], e)`, "the server's rule — 0.25 s
  slack". Her server keeps the joined ranges and measures a re-recorded sentence on them
  (`isStretchHeard` over `heardByClip`); only her screen measures it unjoined.
- `store.ts` `applyHeard`: ranges for a clip are merged into what is stored, never replaced, and
  reset only when the clip's take changes; "The SHORTEST measurement wins: the player reports
  the take record's duration until it has reached the clip's real end, and the real end is what
  the ranges can ever cover."

Decided, as hers (ENG-1419):

- One rule decides a window of one take, a whole part or a sentence laid into one: played
  spans 250 ms or less apart are joined, then cut to the window, and the window is heard when
  what they leave uncovered adds up to at most `min(750 ms, half its length)`. A whole part
  still needs spans and a positive length to be heard at all.
- Spans past a part's end are cut to it. The overrun refusal ("a report that runs past the end
  cannot be about this clip") goes: the report names its take (ADR 0017), so it can no longer
  be about other audio.
- A report with parts adds to what is stored, per take: spans are unioned and kept joined where
  they touch, the length kept is the shortest positive one measured (a zero is no measurement),
  and only entries for the session's current parts are kept, the set the gate asks of. A flat
  report still takes nothing away. This supersedes "a report with parts replaces, it does not
  merge".
- ADR 0070's listen door is the tablet's reporting door: it stores and checks nothing, as
  before, and every answer now carries `unheard_take_ids`, so the tablet never counts by itself
  and the dossier, the release, the refusal and the tablet read one answer.

Rejected: **keeping the gap rule**, which passes a part with seconds unheard; **keeping the
replace and persisting the ledger on the tablet**, because a relaunch and a second tablet on the
session (ENG-1392) would both still erase listening; **a new door**, because the listen door
already stores and checks nothing; **a percentage**, for ADR 0017's reason; **the longest
length**, which would let one inflated measurement block a team that listened.

Consequences: stored reports are re-read under the new rule with no migration. A session in
flight that passed with several short holes adding past 0.75 s is now refused `PART_UNHEARD`,
and the team hears that part again.
