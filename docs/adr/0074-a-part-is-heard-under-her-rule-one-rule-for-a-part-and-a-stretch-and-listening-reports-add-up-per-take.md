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

Decided, as hers except for the length (ENG-1419):

- One rule decides a window of one take, a whole part or a sentence laid into one: played
  spans 250 ms or less apart are joined, then cut to the window, and the window is heard when
  what they leave uncovered adds up to at most `min(750 ms, half its length)`. Any number of
  gaps of 250 ms or less therefore costs nothing, as in her `mergeRanges`; the gaps left after
  the join add up wherever they fall. A whole part still needs spans and a positive length to
  be heard at all.
- Spans past a part's end are cut to it. The overrun refusal ("a report that runs past the end
  cannot be about this clip") goes: the report names its take (ADR 0017), so it can no longer
  be about other audio.
- A part's length is its take's own measured length (`duration_ms`, ENG-1273, ADR 0072)
  whenever the server has one. Only a take with none is measured by the reports: the shortest
  positive length reported, as hers, but never below the end of the furthest stretch standing
  on that take now. The rule lives where the length is read, in one function every reader
  calls (the gate, the listen door, the untranslated parts, the packet, the dossier, the pause
  past the end, a laid-in sentence's `heard_before`); the stored number is never read as is,
  so a row stored before this rule, a part told after its last report, and a write that lands
  beside another are all read the same way. Here
  ours departs from her `applyHeard`: her tablet trusts its own player, while our server knows
  the recording better than the tablet, whose player can still answer with the previous clip's
  length when a part ends. One such length took as the shortest opened a part for good with 2 s
  of 61 played, hid an untranslated tail on the listen door, and turned the pause past the end
  into a permanent refusal.
- A report with parts adds to what is stored, per take: spans are unioned and kept joined where
  they touch. Only the current parts' entries are ever read, so the packet carries the
  listening to the parts Refine receives and an old take's entry is simply never read again.
  A flat report still takes nothing away. Two reports landing together add up too: the write
  that read first adds its entries onto the one that landed. This supersedes "a report with
  parts replaces, it does not merge".
- ADR 0070's listen door is the tablet's reporting door: it stores and checks nothing, as
  before, and every answer now carries `unheard_take_ids`, so the tablet never counts by itself
  and the dossier, the release, the refusal and the tablet read one answer.

Rejected: **keeping the gap rule**, which passes a part with seconds unheard; **keeping the
replace and persisting the ledger on the tablet**, because a relaunch and a second tablet on the
session (ENG-1392) would both still erase listening; **a new door**, because the listen door
already stores and checks nothing; **a percentage**, for ADR 0017's reason; **her shortest
length over a measured take**, for the reason above; **the longest length reported**, which
would let one inflated measurement block a team that listened.

Consequences: stored reports are re-read under the new rule with no migration. A session in
flight that passed with several short holes adding past 0.75 s is now refused `PART_UNHEARD`,
and the team hears that part again. On a take with no measured length, every take uploaded
before ENG-1273, one short report still lowers the bar for good, down to its told end.
