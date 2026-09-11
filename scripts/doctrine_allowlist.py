"""Every site of a forbidden mechanism `check_doctrine.py` already knows about.

Marcia's ruling (04/09) bans six mechanisms from code: word ceilings, probe/station
contracts, memory windows, "say less" notes, a non-frontier model on the voice, and
app-owned conversation modes. Her own guard, `check-doctrine.mjs` in
`Tripod-Internalization`, is green today because the removals it protects have already
happened there. Ours cannot be: every one of the six is still live in
`app/services/internalization_room` and `app/api/internalization_room`, coming out
under a ladder of separate tickets.

So this file is a scan of the sites as they stand *right now* — one entry per file, rule
and offending line's own text, generated from `check_doctrine.scan()` itself run against
that ladder's starting point. An entry names no line number on purpose: eighteen tickets
in that same ladder touch `live_turn.py` alone, and a line-keyed row would go stale on
every edit above it, on a file the ticket never meant to touch. The guard reports every
hit that is not on this list; a hit that is stays silent. Each removal ticket deletes its
rows here in the same commit that deletes the code, and the guard turns fully blocking
the moment the file is empty.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass


class Rule(enum.StrEnum):
    CEILING = "ceiling"
    PROBE = "probe"
    MEMORY_WINDOW = "memory_window"
    SAY_LESS = "say_less"
    MODEL = "model"
    MODE = "mode"


@dataclass(frozen=True)
class AllowlistEntry:
    file: str
    rule: Rule
    text: str


#: Generated from `check_doctrine.scan()`, keyed on (file, rule, text) rather than line
#: (Fable maestri, 2026-09-08) so an edit above a site cannot turn every listed site below
#: it stale. Refreshed 2026-09-09 against `main` after ENG-831 (Assessor/planner/
#: stt_recovery/no_report/render_active_probe_contract deleted), ENG-793's ceiling ticket
#: (word ceilings and "dizendo menos" deleted), and ENG-793's split of run_turn.py into
#: nine modules — 198 sites down to 65: the memory window now lives in validated_turn.py,
#: `gemini_*`/`ThinkingLevel.LOW` in llm.py stay for ENG-747. The mode rule has nothing
#: left to allow: ENG-800 deleted calibration.py, the column, the wire fields and the two
#: prompt sections, so a `bridge_mode` anywhere the guard reads is now a violation with no
#: row to hide behind. ENG-749 then deleted the memory window itself — the whole conversation
#: reaches the Guide every turn — and its two rows went with it: 65 down to 6, every one of
#: them a probe site. Sorted by file, then rule, then the line the text came from, purely for
#: a readable diff.
ALLOWLIST: list[AllowlistEntry] = [
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe.py",
        Rule.PROBE,
        "class ProbePurpose(enum.StrEnum):",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe.py",
        Rule.PROBE,
        "purpose: ProbePurpose",
    ),
]
