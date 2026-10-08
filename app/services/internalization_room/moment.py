from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Any, Literal, NamedTuple

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
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
}

ORDINALS = {
    "primeira": 1,
    "segunda": 2,
    "terceira": 3,
    "quarta": 4,
    "quinta": 5,
    "sexta": 6,
    "sétima": 7,
    "oitava": 8,
    "nona": 9,
    "décima": 10,
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "sixth": 6,
    "seventh": 7,
    "eighth": 8,
    "ninth": 9,
    "tenth": 10,
}
LAST = ("última", "last")


def _alternatives(words: list[str]) -> str:
    return "|".join(sorted(words, key=len, reverse=True))


def _either(portuguese: str, english: str) -> tuple[regex.Pattern[str], ...]:
    return tuple(
        regex.compile(rf"{_START}{line}{_AFTER}", regex.IGNORECASE)
        for line in (portuguese, english)
    )


_N = rf"(\d{{1,2}}|{_alternatives(list(NUMBER_WORDS))})"
_START = r"(?:^|(?<=[.!?…][\"'”\N{RIGHT SINGLE QUOTATION MARK}»)]*\s))"
_LEAD_PT = r"(?:(?:agora|então|bom|ok|muito bem|mas)[,!]?\s+|não,\s+)?"
_LEAD_EN = r"(?:(?:now|so|ok|okay|all right|alright|well|but)[,!]?\s+|no,\s+)?"
_AFTER = r"(?=\s*(?:[.!,:;…—\N{EN DASH}]|$))"
_ORD = rf"({_alternatives([*ORDINALS, *LAST])})"
_PT_PART = rf"(?:(?:cena|parte) {_N}|{_ORD} (?:cena|parte))"
_EN_PART = rf"(?:(?:the )?(?:scene|part) {_N}|the {_ORD} (?:scene|part))"
_APOSTROPHE = r"['\N{RIGHT SINGLE QUOTATION MARK}]"
_ENTRANCE = _either(
    rf"{_LEAD_PT}vamos (?:agora )?(?:pra|para a|para|entrar na|passar (?:pra|para a)"
    rf"|seguir (?:pra|para a)) (Internalização|Articulação) da {_PT_PART}",
    rf"{_LEAD_EN}let{_APOSTROPHE}s (?:now )?(?:go|move|turn)(?: on)? to (?:the )?"
    rf"(Internalization|Articulation) of {_EN_PART}",
)
_WHERE_WE_ARE = _either(
    rf"{_LEAD_PT}(?:ainda )?estamos (?:ainda )?na "
    rf"(?:(Familiarização)|(Internalização|Articulação) da {_PT_PART})",
    rf"{_LEAD_EN}(?:we are|we{_APOSTROPHE}re) (?:still )?in (?:the )?"
    rf"(?:(Familiarization)|(Internalization|Articulation) of {_EN_PART})",
)
_FENCE = _either(
    rf"{_LEAD_PT}(?:agora )?(?:eu )?vou dizer tudo o que deve entrar no ensaio de vocês",
    rf"{_LEAD_EN}(?:now )?I(?: will|{_APOSTROPHE}ll) (?:say|tell you) everything that should go "
    r"into your rehearsal",
)
_ENTRANCES: dict[str, tuple[str, At]] = {
    "internalização": ("entrance", "internalization"),
    "internalization": ("entrance", "internalization"),
    "articulação": ("articulation_entrance", "articulation"),
    "articulation": ("articulation_entrance", "articulation"),
}

FAMILIARIZATION_CLOSINGS = (
    "O que chamou a atenção de vocês nessa passagem? Conversem entre vocês. Se tiver alguma "
    "dúvida, me perguntem. Quando estiverem prontos, me digam e a gente vai pra Internalização "
    "da primeira cena.",
    "What caught your attention in this passage? Talk it over among yourselves. If you have any "
    "questions, ask me. When you are ready, tell me and we will move to Internalization of the "
    "first scene.",
)
SCENE_CLOSINGS = (
    "O que chamou a atenção de vocês nessa cena? Conversem entre vocês. Essa cena ficou clara? "
    "Se tiver alguma dúvida, me perguntem. Se já entenderam, me digam e a gente vai pro ensaio.",
    "What caught your attention in this scene? Talk it over among yourselves. Is this scene "
    "clear? If you have any questions, ask me. If you have understood it, tell me and we will "
    "go to the rehearsal.",
    "O que chamou a atenção de vocês nessa parte? Conversem entre vocês. Essa parte ficou clara? "
    "Se tiver alguma dúvida, me perguntem. Se já entenderam, me digam e a gente vai pro ensaio.",
    "What caught your attention in this part? Talk it over among yourselves. Is this part clear? "
    "If you have any questions, ask me. If you have understood it, tell me and we will go to "
    "the rehearsal.",
)
SEND_OFFS = (
    "Agora toquem no ponto laranja, no alto da tela, para abrir o Ensaio Final.",
    "Now tap the orange dot at the top of the screen to open the Final Rehearsal.",
)


def _folded(voiced: str) -> str:
    return " ".join(unicodedata.normalize("NFC", voiced).split())


def _found(detectors: tuple[regex.Pattern[str], ...], folded: str) -> list[regex.Match[str]]:
    return [line for detector in detectors for line in detector.finditer(folded)]


def _number(said: str | None, ordinal: str | None, parts: int) -> int:
    if said is not None:
        return int(said) if said.isdigit() else NUMBER_WORDS[said.lower()]
    named = (ordinal or "").lower()
    return parts if named in LAST else ORDINALS[named]


@dataclass(frozen=True)
class Moment:
    """Her `Moment` (`src/session/types.ts`, app 18fa7c4), stored in her JSON shape."""

    at: At
    part: int | None = None
    closed: bool = False
    fenced: bool = False

    def as_json(self) -> dict[str, Any]:
        stored: dict[str, Any] = {"at": self.at}
        if self.part is not None:
            stored["part"] = self.part
        if self.closed:
            stored["closed"] = True
        if self.at == "articulation":
            stored["fenced"] = self.fenced
        return stored

    @classmethod
    def of(cls, stored: dict[str, Any]) -> Moment:
        return cls(
            at=stored["at"],
            part=stored.get("part"),
            closed=stored.get("closed", False),
            fenced=stored.get("fenced", False),
        )


FAMILIARIZATION = Moment(at="familiarization")


def moment_at_turn_start(messages: list[dict[str, Any]]) -> Moment | None:
    """Where the last guide entry left the room; the Familiarization for a conversation still
    empty, and none for a session whose turns were kept before the moment was read."""
    guides = [message for message in messages if message["role"] == "guide"]
    if not guides:
        return FAMILIARIZATION
    step = guides[-1].get("moment")
    return None if step is None else Moment.of(step["after"])


def moment_step(
    messages: list[dict[str, Any]], voiced: str, *, fail_safe: bool, parts: int
) -> dict[str, Any] | None:
    """Her MomentStep: where the lines this reply voiced leave the moment the turn began in.
    A fixed line that answered in the Guide's place moves nothing (moment.ts:270)."""
    before = moment_at_turn_start(messages)
    if before is None:
        return None
    after = before
    by: list[str] = []
    for line in [] if fail_safe else _triggers(_folded(voiced), parts):
        if line.part is not None and not 1 <= line.part <= parts:
            continue
        moved = _moved(after, line)
        if moved != after:
            by.append(line.cause)
        after = moved
    return {"before": before.as_json(), "after": after.as_json(), "by": by}


class _Line(NamedTuple):
    at: int
    cause: str
    part: int | None = None
    to: At | None = None


def _triggers(folded: str, parts: int) -> list[_Line]:
    found = []
    for line in _found(_ENTRANCE, folded):
        cause, to = _ENTRANCES[line[1].lower()]
        part = _number(line[2], line[3], parts)
        found.append(_Line(line.start(), cause, part=part, to=to))
    for line in _found(_WHERE_WE_ARE, folded):
        if line[1]:
            found.append(_Line(line.start(), "where_we_are", to="familiarization"))
        else:
            to = _ENTRANCES[line[2].lower()][1]
            part = _number(line[3], line[4], parts)
            found.append(_Line(line.start(), "where_we_are", part=part, to=to))
    found += [_Line(line.start(), "fence") for line in _found(_FENCE, folded)]
    for cause, lines in (
        ("part_closing", SCENE_CLOSINGS),
        ("familiarization_closing", FAMILIARIZATION_CLOSINGS),
        ("send_off", SEND_OFFS),
    ):
        for said in lines:
            if folded.endswith(said):
                found.append(_Line(len(folded) - len(said), cause))
                break
    return sorted(found, key=lambda line: line.at)


def _moved(moment: Moment, line: _Line) -> Moment:
    if line.cause == "send_off":
        return Moment(at="ensaio_final")
    if moment.at == "ensaio_final":
        return moment
    if line.to == "familiarization":
        return moment if moment.at == "familiarization" else FAMILIARIZATION
    if line.to == "internalization":
        return Moment(at="internalization", part=line.part)
    if line.to == "articulation":
        same = moment.at == "articulation" and moment.part == line.part
        return moment if same else Moment(at="articulation", part=line.part)
    if line.cause == "fence":
        fenced = Moment(at="articulation", part=moment.part, fenced=True)
        return moment if moment.at == "familiarization" else fenced
    if moment.at != "familiarization":
        return moment
    if line.cause == "part_closing":
        return Moment(at="internalization", part=1) if moment.closed else moment
    return Moment(at="familiarization", closed=True)


def moment_fact(messages: list[dict[str, Any]], pericope_num: str) -> str:
    """Her MOMENT fact (`src/turn/moment.ts` renderMoment, app 18fa7c4): where the room is,
    read from the lines the team heard — information for the Guide, never an instruction."""
    moment = moment_at_turn_start(messages)
    if moment is None:
        return ""
    parts = len(scene_ids_for(pericope_num))
    if moment.at == "internalization":
        return f"MOMENT: Internalization of part {moment.part} of {parts} {_DASH} the part is open."
    if moment.at == "articulation":
        given = f" {_DASH} its fenced block has been given" if moment.fenced else ""
        return f"MOMENT: Articulation of part {moment.part} of {parts}{given}."
    if moment.at == "ensaio_final":
        return f"MOMENT: Ensaio Final (Final Rehearsal) {_DASH} the send-off has been given."
    if moment.closed:
        return (
            f"MOMENT: Familiarization {_DASH} its closing has been said; "
            "no part has been opened yet."
        )
    return f"MOMENT: Familiarization {_DASH} the whole passage; no part has been opened yet."
