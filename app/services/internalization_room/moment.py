from __future__ import annotations

from typing import Any


def moment_fact(messages: list[dict[str, Any]], pericope_num: str) -> str:
    """Her MOMENT fact (`src/turn/moment.ts` renderMoment, app 18fa7c4): where the room is,
    read from the lines the team heard — information for the Guide, never an instruction."""
    return "MOMENT: Familiarization \N{EM DASH} the whole passage; no part has been opened yet."
