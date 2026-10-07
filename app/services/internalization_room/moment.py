from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import regex

At = Literal["familiarization", "internalization", "articulation", "ensaio_final"]

_ENTRANCE = regex.compile(r"vamos pra (Internalização) da cena (\d{1,2})\.", regex.IGNORECASE)


@dataclass(frozen=True)
class Moment:
    """Her `Moment` (`src/session/types.ts`, app 18fa7c4), stored in her JSON shape."""

    at: At
    part: int | None = None

    def as_json(self) -> dict[str, Any]:
        return {"at": self.at} | ({} if self.part is None else {"part": self.part})

    @classmethod
    def of(cls, stored: dict[str, Any]) -> Moment:
        return cls(at=stored["at"], part=stored.get("part"))


FAMILIARIZATION = Moment(at="familiarization")


def moment_at_turn_start(messages: list[dict[str, Any]]) -> Moment:
    guides = [message for message in messages if message["role"] == "guide"]
    return Moment.of(guides[-1]["moment"]["after"]) if guides else FAMILIARIZATION


def moment_step(messages: list[dict[str, Any]], voiced: str) -> dict[str, Any]:
    """Her MomentStep: where the lines this reply voiced leave the moment the turn began in."""
    before = moment_at_turn_start(messages)
    after = before
    by: list[str] = []
    for line in _ENTRANCE.finditer(voiced):
        after = Moment(at="internalization", part=int(line[2]))
        by.append("entrance")
    return {"before": before.as_json(), "after": after.as_json(), "by": by}


def moment_fact(messages: list[dict[str, Any]], pericope_num: str) -> str:
    """Her MOMENT fact (`src/turn/moment.ts` renderMoment, app 18fa7c4): where the room is,
    read from the lines the team heard — information for the Guide, never an instruction."""
    return "MOMENT: Familiarization \N{EM DASH} the whole passage; no part has been opened yet."
