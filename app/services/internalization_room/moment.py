from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Any, Literal

import regex

from app.services.internalization_room.comprehension.checkpoints import scene_ids_for

_DASH = "\N{EM DASH}"

At = Literal["familiarization", "internalization", "articulation", "ensaio_final"]

NUMBER_WORDS = {
    "um": 1,
    "uma": 1,
    "dois": 2,
    "duas": 2,
    "três": 3,
    "quatro": 4,
    "cinco": 5,
    "seis": 6,
    "sete": 7,
    "oito": 8,
    "nove": 9,
    "dez": 10,
    "onze": 11,
    "doze": 12,
}


def _alternatives(words: list[str]) -> str:
    return "|".join(sorted(words, key=len, reverse=True))


_N = rf"(\d{{1,2}}|{_alternatives(list(NUMBER_WORDS))})"
_START = r"(?:^|(?<=[.!?…][\"'”\N{RIGHT SINGLE QUOTATION MARK}»)]*\s))"
_LEAD_PT = r"(?:(?:agora|então|bom|ok|muito bem|mas)[,!]?\s+|não,\s+)?"
_AFTER = r"(?=\s*(?:[.!,:;…—\N{EN DASH}]|$))"
_PT_PART = rf"(?:cena|parte) {_N}"
_ENTRANCE = regex.compile(
    rf"{_START}{_LEAD_PT}vamos (?:agora )?(?:pra|para a|para|entrar na|passar (?:pra|para a)"
    rf"|seguir (?:pra|para a)) (Internalização) da {_PT_PART}{_AFTER}",
    regex.IGNORECASE,
)


FAMILIARIZATION_CLOSING = (
    "O que chamou a atenção de vocês nessa passagem? Conversem entre vocês. Se tiver alguma "
    "dúvida, me perguntem. Quando estiverem prontos, me digam e a gente vai pra Internalização "
    "da primeira cena."
)

SCENE_CLOSINGS = (
    "O que chamou a atenção de vocês nessa cena? Conversem entre vocês. Essa cena ficou clara? "
    "Se tiver alguma dúvida, me perguntem. Se já entenderam, me digam e a gente vai pro ensaio.",
    "O que chamou a atenção de vocês nessa parte? Conversem entre vocês. Essa parte ficou clara? "
    "Se tiver alguma dúvida, me perguntem. Se já entenderam, me digam e a gente vai pro ensaio.",
)

SEND_OFF_LAST = "Agora toquem no ponto laranja, no alto da tela, para abrir o Ensaio Final."


def _folded(voiced: str) -> str:
    return " ".join(unicodedata.normalize("NFC", voiced).split())


def _number(word: str) -> int:
    return int(word) if word.isdigit() else NUMBER_WORDS[word.lower()]


@dataclass(frozen=True)
class Moment:
    """Her `Moment` (`src/session/types.ts`, app 18fa7c4), stored in her JSON shape."""

    at: At
    part: int | None = None
    closed: bool = False

    def as_json(self) -> dict[str, Any]:
        stored: dict[str, Any] = {"at": self.at}
        if self.part is not None:
            stored["part"] = self.part
        if self.closed:
            stored["closed"] = True
        return stored

    @classmethod
    def of(cls, stored: dict[str, Any]) -> Moment:
        return cls(at=stored["at"], part=stored.get("part"), closed=stored.get("closed", False))


FAMILIARIZATION = Moment(at="familiarization")


def moment_at_turn_start(messages: list[dict[str, Any]]) -> Moment:
    guides = [message for message in messages if message["role"] == "guide"]
    return Moment.of(guides[-1]["moment"]["after"]) if guides else FAMILIARIZATION


def moment_step(messages: list[dict[str, Any]], voiced: str) -> dict[str, Any]:
    """Her MomentStep: where the lines this reply voiced leave the moment the turn began in."""
    before = moment_at_turn_start(messages)
    after = before
    by: list[str] = []
    for _, cause, part in _triggers(_folded(voiced)):
        moved = _moved(after, cause, part)
        if moved != after:
            by.append(cause)
        after = moved
    return {"before": before.as_json(), "after": after.as_json(), "by": by}


def _triggers(folded: str) -> list[tuple[int, str, int | None]]:
    found: list[tuple[int, str, int | None]] = [
        (line.start(), "entrance", _number(line[2])) for line in _ENTRANCE.finditer(folded)
    ]
    for cause, lines in (
        ("part_closing", SCENE_CLOSINGS),
        ("familiarization_closing", (FAMILIARIZATION_CLOSING,)),
        ("send_off", (SEND_OFF_LAST,)),
    ):
        for line in lines:
            if folded.endswith(line):
                found.append((len(folded) - len(line), cause, None))
                break
    return sorted(found)


def _moved(moment: Moment, cause: str, part: int | None) -> Moment:
    if cause == "send_off":
        return Moment(at="ensaio_final")
    if moment.at == "ensaio_final":
        return moment
    if cause == "entrance":
        return Moment(at="internalization", part=part)
    if moment.at != "familiarization":
        return moment
    if cause == "part_closing":
        return Moment(at="internalization", part=1) if moment.closed else moment
    return Moment(at="familiarization", closed=True)


def moment_fact(messages: list[dict[str, Any]], pericope_num: str) -> str:
    """Her MOMENT fact (`src/turn/moment.ts` renderMoment, app 18fa7c4): where the room is,
    read from the lines the team heard — information for the Guide, never an instruction."""
    moment = moment_at_turn_start(messages)
    parts = len(scene_ids_for(pericope_num))
    if moment.at == "internalization":
        return f"MOMENT: Internalization of part {moment.part} of {parts} {_DASH} the part is open."
    if moment.closed:
        return (
            f"MOMENT: Familiarization {_DASH} its closing has been said; "
            "no part has been opened yet."
        )
    return f"MOMENT: Familiarization {_DASH} the whole passage; no part has been opened yet."
