"""Whether a release overruled the gate, read from what it waived and never from a flag.

The row is the truth about who pressed and when; this is the truth about whether the gate was
shut. A release a force minted over an open gate before ADR 0080 keeps who pressed and reads as
an ordinary approval, so every reader asks here and none reads ``forced_at`` or the packet's
``check.forced`` on its own. A force stored before ``forced_blockers`` existed has none, which
is not having waived nothing, and stays forced (ENG-1305).
"""

from __future__ import annotations


def was_forced(forced_by: str | None, forced_blockers: list[str] | None) -> bool:
    return forced_by is not None and forced_blockers != []
