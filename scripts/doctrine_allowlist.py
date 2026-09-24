"""Every site of a forbidden mechanism `check_doctrine.py` already knows about.

Marcia's ruling (04/09) bans six mechanisms from code: word ceilings, probe/station
contracts, memory windows, "say less" notes, a non-frontier model on the voice, and
app-owned conversation modes. Her own guard, `check-doctrine.mjs` in
`Tripod-Internalization`, is green because the removals it protects had already happened
there. Ours could not be at first: every one of the six was still live in
`app/services/internalization_room` and `app/api/internalization_room`, and came out
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


ALLOWLIST: list[AllowlistEntry] = []
