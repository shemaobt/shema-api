"""Every site of a forbidden mechanism `check_doctrine.py` already knows about.

Marcia's ruling (04/09) bans six mechanisms from code: word ceilings, probe/station
contracts, memory windows, "say less" notes, a non-frontier model on the voice, and
app-owned conversation modes. Her own guard, `check-doctrine.mjs` in
`Tripod-Internalization`, is green today because the removals it protects have already
happened there. Ours cannot be: every one of the six is still live in
`app/services/internalization_room` and `app/api/internalization_room`, coming out
under a ladder of separate tickets.

So this file is a scan of the sites as they stand *right now* — one entry per file, line
and rule, generated from `check_doctrine.scan()` itself run against that ladder's
starting point. The guard reports every hit that is not on this list; a hit that is
stays silent. Each removal ticket deletes its rows here in the same commit that deletes
the code, and the guard turns fully blocking the moment the file is empty.
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
    line: int
    rule: Rule


#: Generated from `check_doctrine.scan()` against the ladder's starting point (2026-09-08).
#: One entry per (file, line, rule) the guard finds today. Sorted by file, then line, so a
#: removal ticket's diff against this list is exactly the rows it deletes.
ALLOWLIST: list[AllowlistEntry] = [
    AllowlistEntry("app/api/internalization_room/sessions.py", 41, Rule.MODE),
    AllowlistEntry("app/api/internalization_room/sessions.py", 185, Rule.MODE),
    AllowlistEntry("app/api/internalization_room/sessions.py", 249, Rule.MODE),
    AllowlistEntry("app/api/internalization_room/sessions.py", 444, Rule.MODE),
    AllowlistEntry("app/api/internalization_room/sessions.py", 512, Rule.MODE),
    AllowlistEntry("app/api/internalization_room/sessions.py", 518, Rule.MODE),
    AllowlistEntry("app/api/internalization_room/sessions.py", 521, Rule.MODE),
    AllowlistEntry("app/api/internalization_room/sessions.py", 528, Rule.MODE),
    AllowlistEntry("app/api/internalization_room/sessions.py", 530, Rule.MODE),
    AllowlistEntry("app/api/internalization_room/sessions.py", 544, Rule.CEILING),
    AllowlistEntry("app/api/internalization_room/sessions.py", 549, Rule.MODE),
    AllowlistEntry("app/api/internalization_room/sessions.py", 566, Rule.MODE),
    AllowlistEntry("app/api/internalization_room/sessions.py", 595, Rule.MODE),
    AllowlistEntry("app/db/models/internalization_room.py", 87, Rule.MODE),
    AllowlistEntry("app/models/internalization_room.py", 277, Rule.MODE),
    AllowlistEntry("app/models/internalization_room.py", 371, Rule.MODE),
    AllowlistEntry("app/models/internalization_room.py", 372, Rule.MODE),
    AllowlistEntry("app/models/internalization_room.py", 408, Rule.MODE),
    AllowlistEntry("app/services/internalization_room/__init__.py", 20, Rule.CEILING),
    AllowlistEntry("app/services/internalization_room/__init__.py", 21, Rule.CEILING),
    AllowlistEntry("app/services/internalization_room/__init__.py", 57, Rule.MODE),
    AllowlistEntry("app/services/internalization_room/__init__.py", 65, Rule.CEILING),
    AllowlistEntry("app/services/internalization_room/__init__.py", 66, Rule.CEILING),
    AllowlistEntry("app/services/internalization_room/__init__.py", 109, Rule.MODE),
    AllowlistEntry("app/services/internalization_room/calibration.py", 32, Rule.MODE),
    AllowlistEntry("app/services/internalization_room/calibration.py", 33, Rule.MODE),
    AllowlistEntry("app/services/internalization_room/calibration.py", 42, Rule.MODE),
    AllowlistEntry("app/services/internalization_room/calibration.py", 234, Rule.MODE),
    AllowlistEntry("app/services/internalization_room/calibration.py", 267, Rule.MODE),
    AllowlistEntry("app/services/internalization_room/calibration.py", 268, Rule.PROBE),
    AllowlistEntry("app/services/internalization_room/calibration.py", 271, Rule.MODE),
    AllowlistEntry("app/services/internalization_room/calibration.py", 272, Rule.MODE),
    AllowlistEntry("app/services/internalization_room/comprehension/assessor.py", 491, Rule.MODE),
    AllowlistEntry("app/services/internalization_room/comprehension/no_report.py", 16, Rule.PROBE),
    AllowlistEntry("app/services/internalization_room/comprehension/no_report.py", 31, Rule.PROBE),
    AllowlistEntry("app/services/internalization_room/comprehension/practice.py", 21, Rule.PROBE),
    AllowlistEntry("app/services/internalization_room/comprehension/practice.py", 22, Rule.PROBE),
    AllowlistEntry("app/services/internalization_room/comprehension/practice.py", 254, Rule.PROBE),
    AllowlistEntry("app/services/internalization_room/comprehension/practice.py", 256, Rule.PROBE),
    AllowlistEntry("app/services/internalization_room/comprehension/practice.py", 446, Rule.PROBE),
    AllowlistEntry("app/services/internalization_room/comprehension/practice.py", 447, Rule.PROBE),
    AllowlistEntry("app/services/internalization_room/comprehension/probe.py", 29, Rule.PROBE),
    AllowlistEntry("app/services/internalization_room/comprehension/probe.py", 30, Rule.PROBE),
    AllowlistEntry("app/services/internalization_room/comprehension/probe.py", 31, Rule.PROBE),
    AllowlistEntry("app/services/internalization_room/comprehension/probe.py", 40, Rule.PROBE),
    AllowlistEntry("app/services/internalization_room/comprehension/probe.py", 42, Rule.PROBE),
    AllowlistEntry("app/services/internalization_room/comprehension/probe.py", 43, Rule.PROBE),
    AllowlistEntry("app/services/internalization_room/comprehension/probe.py", 44, Rule.PROBE),
    AllowlistEntry("app/services/internalization_room/comprehension/probe.py", 45, Rule.PROBE),
    AllowlistEntry("app/services/internalization_room/comprehension/probe.py", 54, Rule.PROBE),
    AllowlistEntry("app/services/internalization_room/comprehension/probe.py", 62, Rule.PROBE),
    AllowlistEntry("app/services/internalization_room/comprehension/probe.py", 78, Rule.PROBE),
    AllowlistEntry("app/services/internalization_room/comprehension/probe.py", 83, Rule.PROBE),
    AllowlistEntry("app/services/internalization_room/comprehension/probe.py", 88, Rule.PROBE),
    AllowlistEntry("app/services/internalization_room/comprehension/probe.py", 101, Rule.PROBE),
    AllowlistEntry("app/services/internalization_room/comprehension/probe.py", 102, Rule.PROBE),
    AllowlistEntry("app/services/internalization_room/comprehension/probe.py", 103, Rule.PROBE),
    AllowlistEntry("app/services/internalization_room/comprehension/probe.py", 104, Rule.PROBE),
    AllowlistEntry("app/services/internalization_room/comprehension/probe.py", 110, Rule.PROBE),
    AllowlistEntry("app/services/internalization_room/comprehension/probe.py", 115, Rule.PROBE),
    AllowlistEntry("app/services/internalization_room/comprehension/probe.py", 122, Rule.PROBE),
    AllowlistEntry("app/services/internalization_room/comprehension/probe.py", 123, Rule.PROBE),
    AllowlistEntry("app/services/internalization_room/comprehension/probe.py", 126, Rule.MODE),
    AllowlistEntry("app/services/internalization_room/comprehension/probe.py", 133, Rule.PROBE),
    AllowlistEntry("app/services/internalization_room/comprehension/probe.py", 158, Rule.PROBE),
    AllowlistEntry("app/services/internalization_room/comprehension/probe.py", 210, Rule.PROBE),
    AllowlistEntry("app/services/internalization_room/comprehension/probe_plan.py", 25, Rule.PROBE),
    AllowlistEntry("app/services/internalization_room/comprehension/probe_plan.py", 27, Rule.PROBE),
    AllowlistEntry("app/services/internalization_room/comprehension/probe_plan.py", 56, Rule.MODE),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py", 194, Rule.PROBE
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py", 204, Rule.PROBE
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py", 228, Rule.PROBE
    ),
    AllowlistEntry("app/services/internalization_room/comprehension/probe_plan.py", 241, Rule.MODE),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py", 249, Rule.PROBE
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py", 258, Rule.PROBE
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py", 270, Rule.PROBE
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py", 280, Rule.PROBE
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py", 306, Rule.PROBE
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py", 317, Rule.PROBE
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py", 328, Rule.PROBE
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py", 335, Rule.PROBE
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py", 342, Rule.PROBE
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py", 344, Rule.PROBE
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py", 347, Rule.PROBE
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py", 348, Rule.PROBE
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py", 359, Rule.PROBE
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py", 372, Rule.PROBE
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py", 381, Rule.PROBE
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py", 388, Rule.PROBE
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py", 396, Rule.PROBE
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py", 447, Rule.PROBE
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py", 457, Rule.PROBE
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py", 463, Rule.PROBE
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py", 474, Rule.PROBE
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py", 496, Rule.PROBE
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py", 504, Rule.PROBE
    ),
    AllowlistEntry("app/services/internalization_room/comprehension/state.py", 5, Rule.MODE),
    AllowlistEntry("app/services/internalization_room/live_turn.py", 34, Rule.MODE),
    AllowlistEntry("app/services/internalization_room/live_turn.py", 35, Rule.MODE),
    AllowlistEntry("app/services/internalization_room/live_turn.py", 36, Rule.MODE),
    AllowlistEntry("app/services/internalization_room/live_turn.py", 65, Rule.PROBE),
    AllowlistEntry("app/services/internalization_room/live_turn.py", 66, Rule.PROBE),
    AllowlistEntry("app/services/internalization_room/live_turn.py", 67, Rule.MODE),
    AllowlistEntry("app/services/internalization_room/live_turn.py", 74, Rule.PROBE),
    AllowlistEntry("app/services/internalization_room/live_turn.py", 75, Rule.PROBE),
    AllowlistEntry("app/services/internalization_room/live_turn.py", 106, Rule.CEILING),
    AllowlistEntry("app/services/internalization_room/live_turn.py", 107, Rule.CEILING),
    AllowlistEntry("app/services/internalization_room/live_turn.py", 108, Rule.CEILING),
    AllowlistEntry("app/services/internalization_room/live_turn.py", 109, Rule.CEILING),
    AllowlistEntry("app/services/internalization_room/live_turn.py", 122, Rule.MODE),
    AllowlistEntry("app/services/internalization_room/live_turn.py", 141, Rule.CEILING),
    AllowlistEntry("app/services/internalization_room/live_turn.py", 151, Rule.CEILING),
    AllowlistEntry("app/services/internalization_room/live_turn.py", 153, Rule.CEILING),
    AllowlistEntry("app/services/internalization_room/live_turn.py", 154, Rule.CEILING),
    AllowlistEntry("app/services/internalization_room/live_turn.py", 234, Rule.MODE),
    AllowlistEntry("app/services/internalization_room/live_turn.py", 236, Rule.MODE),
    AllowlistEntry("app/services/internalization_room/live_turn.py", 238, Rule.MODE),
    AllowlistEntry("app/services/internalization_room/live_turn.py", 240, Rule.MODE),
    AllowlistEntry("app/services/internalization_room/live_turn.py", 243, Rule.PROBE),
    AllowlistEntry("app/services/internalization_room/live_turn.py", 276, Rule.PROBE),
    AllowlistEntry("app/services/internalization_room/live_turn.py", 294, Rule.MODE),
    AllowlistEntry("app/services/internalization_room/live_turn.py", 295, Rule.MODE),
    AllowlistEntry("app/services/internalization_room/live_turn.py", 352, Rule.PROBE),
    AllowlistEntry("app/services/internalization_room/live_turn.py", 417, Rule.PROBE),
    AllowlistEntry("app/services/internalization_room/live_turn.py", 457, Rule.MODE),
    AllowlistEntry("app/services/internalization_room/live_turn.py", 476, Rule.PROBE),
    AllowlistEntry("app/services/internalization_room/live_turn.py", 481, Rule.MODE),
    AllowlistEntry("app/services/internalization_room/live_turn.py", 488, Rule.PROBE),
    AllowlistEntry("app/services/internalization_room/live_turn.py", 497, Rule.PROBE),
    AllowlistEntry("app/services/internalization_room/live_turn.py", 508, Rule.PROBE),
    AllowlistEntry("app/services/internalization_room/live_turn.py", 511, Rule.MODE),
    AllowlistEntry("app/services/internalization_room/live_turn.py", 519, Rule.MODE),
    AllowlistEntry("app/services/internalization_room/live_turn.py", 520, Rule.MODE),
    AllowlistEntry("app/services/internalization_room/live_turn.py", 532, Rule.MODE),
    AllowlistEntry("app/services/internalization_room/live_turn.py", 552, Rule.PROBE),
    AllowlistEntry("app/services/internalization_room/live_turn.py", 560, Rule.PROBE),
    AllowlistEntry("app/services/internalization_room/live_turn.py", 564, Rule.PROBE),
    AllowlistEntry("app/services/internalization_room/live_turn.py", 569, Rule.PROBE),
    AllowlistEntry("app/services/internalization_room/live_turn.py", 578, Rule.MODE),
    AllowlistEntry("app/services/internalization_room/live_turn.py", 581, Rule.MODE),
    AllowlistEntry("app/services/internalization_room/live_turn.py", 651, Rule.CEILING),
    AllowlistEntry("app/services/internalization_room/live_turn.py", 694, Rule.MODE),
    AllowlistEntry("app/services/internalization_room/llm.py", 15, Rule.MODEL),
    AllowlistEntry("app/services/internalization_room/llm.py", 18, Rule.MODEL),
    AllowlistEntry("app/services/internalization_room/prepare_opening.py", 13, Rule.CEILING),
    AllowlistEntry("app/services/internalization_room/prepare_opening.py", 62, Rule.CEILING),
    AllowlistEntry("app/services/internalization_room/rehearsal_readiness.py", 14, Rule.PROBE),
    AllowlistEntry("app/services/internalization_room/rehearsal_readiness.py", 177, Rule.PROBE),
    AllowlistEntry("app/services/internalization_room/release.py", 218, Rule.MODE),
    AllowlistEntry("app/services/internalization_room/release.py", 277, Rule.MODE),
    AllowlistEntry("app/services/internalization_room/run_turn.py", 23, Rule.MEMORY_WINDOW),
    AllowlistEntry("app/services/internalization_room/run_turn.py", 67, Rule.CEILING),
    AllowlistEntry("app/services/internalization_room/run_turn.py", 68, Rule.CEILING),
    AllowlistEntry("app/services/internalization_room/run_turn.py", 70, Rule.CEILING),
    AllowlistEntry("app/services/internalization_room/run_turn.py", 71, Rule.CEILING),
    AllowlistEntry("app/services/internalization_room/run_turn.py", 75, Rule.CEILING),
    AllowlistEntry("app/services/internalization_room/run_turn.py", 76, Rule.CEILING),
    AllowlistEntry("app/services/internalization_room/run_turn.py", 80, Rule.CEILING),
    AllowlistEntry("app/services/internalization_room/run_turn.py", 99, Rule.CEILING),
    AllowlistEntry("app/services/internalization_room/run_turn.py", 100, Rule.CEILING),
    AllowlistEntry("app/services/internalization_room/run_turn.py", 101, Rule.CEILING),
    AllowlistEntry("app/services/internalization_room/run_turn.py", 102, Rule.CEILING),
    AllowlistEntry("app/services/internalization_room/run_turn.py", 103, Rule.CEILING),
    AllowlistEntry("app/services/internalization_room/run_turn.py", 105, Rule.CEILING),
    AllowlistEntry("app/services/internalization_room/run_turn.py", 106, Rule.CEILING),
    AllowlistEntry("app/services/internalization_room/run_turn.py", 107, Rule.CEILING),
    AllowlistEntry("app/services/internalization_room/run_turn.py", 115, Rule.CEILING),
    AllowlistEntry("app/services/internalization_room/run_turn.py", 139, Rule.CEILING),
    AllowlistEntry("app/services/internalization_room/run_turn.py", 142, Rule.CEILING),
    AllowlistEntry("app/services/internalization_room/run_turn.py", 225, Rule.MEMORY_WINDOW),
    AllowlistEntry("app/services/internalization_room/run_turn.py", 385, Rule.CEILING),
    AllowlistEntry("app/services/internalization_room/run_turn.py", 489, Rule.CEILING),
    AllowlistEntry("app/services/internalization_room/run_turn.py", 491, Rule.CEILING),
    AllowlistEntry("app/services/internalization_room/run_turn.py", 493, Rule.CEILING),
    AllowlistEntry("app/services/internalization_room/run_turn.py", 553, Rule.CEILING),
    AllowlistEntry("app/services/internalization_room/run_turn.py", 616, Rule.CEILING),
    AllowlistEntry("app/services/internalization_room/run_turn.py", 745, Rule.CEILING),
    AllowlistEntry("app/services/internalization_room/run_turn.py", 745, Rule.SAY_LESS),
    AllowlistEntry("app/services/internalization_room/run_turn.py", 785, Rule.SAY_LESS),
    AllowlistEntry("app/services/internalization_room/run_turn.py", 786, Rule.SAY_LESS),
    AllowlistEntry("app/services/internalization_room/run_turn.py", 793, Rule.SAY_LESS),
    AllowlistEntry("app/services/internalization_room/run_turn.py", 797, Rule.SAY_LESS),
    AllowlistEntry("app/services/internalization_room/run_turn.py", 809, Rule.CEILING),
    AllowlistEntry("app/services/internalization_room/run_turn.py", 817, Rule.CEILING),
    AllowlistEntry("app/services/internalization_room/run_turn.py", 818, Rule.CEILING),
    AllowlistEntry("app/services/internalization_room/run_turn.py", 819, Rule.CEILING),
    AllowlistEntry("app/services/internalization_room/run_turn.py", 819, Rule.SAY_LESS),
    AllowlistEntry("app/services/internalization_room/sessions.py", 17, Rule.MODE),
    AllowlistEntry("app/services/internalization_room/sessions.py", 81, Rule.MODE),
    AllowlistEntry("app/services/internalization_room/sessions.py", 140, Rule.MODE),
    AllowlistEntry("app/services/internalization_room/sessions.py", 141, Rule.MODE),
    AllowlistEntry("app/services/internalization_room/sessions.py", 145, Rule.MODE),
    AllowlistEntry("app/services/internalization_room/sessions.py", 146, Rule.MODE),
    AllowlistEntry("app/services/internalization_room/sessions.py", 160, Rule.MODE),
    AllowlistEntry("app/services/internalization_room/sessions.py", 270, Rule.MODE),
    AllowlistEntry("app/services/internalization_room/sessions.py", 271, Rule.MODE),
    AllowlistEntry("app/services/internalization_room/sessions.py", 273, Rule.MODE),
    AllowlistEntry("app/services/internalization_room/sessions.py", 295, Rule.MODE),
]
