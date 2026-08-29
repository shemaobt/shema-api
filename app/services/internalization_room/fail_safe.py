from __future__ import annotations

import enum
import re
from functools import lru_cache

from app.services.internalization_room._default_prompts import fail_safe_utterances


class FailSafe(enum.StrEnum):
    UNREPAIRABLE = "A"
    OUTSIDE_MAP = "B"
    HANDOFF = "C"
    INAUDIBLE = "D"
    HARD_STOP = "E"
    INSTANT_ACK = "F"
    OFF_BRIDGE_LANGUAGE = "G"
    UNTOLD_STRETCH = "H"


_SECTION = re.compile(r"^### ([A-Z])(-([a-z]{2}))?\.", re.M)
_BULLET = re.compile(r'^- "(.+)"$', re.M)


@lru_cache(maxsize=1)
def _sections() -> dict[tuple[str, str | None], list[str]]:
    text = fail_safe_utterances()
    marks = list(_SECTION.finditer(text))
    parsed: dict[tuple[str, str | None], list[str]] = {}
    for index, mark in enumerate(marks):
        end = marks[index + 1].start() if index + 1 < len(marks) else len(text)
        body = text[mark.end() : end]
        parsed[(mark.group(1), mark.group(3))] = _BULLET.findall(body)
    return parsed


def utterances(kind: FailSafe, language_code: str = "pt") -> list[str]:
    """The pre-approved lines for one situation, in the session language when written.

    These are application strings, not a model call — the whole point of the fail-safe is
    that nothing generative stands between the failure and what the team hears.
    """
    sections = _sections()
    localized = sections.get((str(kind), language_code))
    if localized:
        return localized
    return sections.get((str(kind), None), [])


def first(kind: FailSafe, language_code: str = "pt") -> str:
    lines = utterances(kind, language_code)
    return lines[0] if lines else ""


def choose(kind: FailSafe, language_code: str = "pt", *, turn: int = 0) -> tuple[str, str]:
    """One line for this situation, and the name the app knows it by.

    Rotating with the turn is what the authored file asks for — *"vary them, don't repeat
    the same line twice running, so the session doesn't feel robotic"* — and a room that
    answers two failures in a row with the identical sentence sounds like a machine stuck,
    which is the one impression the fail-safe exists to avoid.

    The name is what the app plays: these lines are shipped as audio inside the app, so a
    failure costs no synthesis and needs no network — which matters, because the network is
    often what failed.
    """
    lines = utterances(kind, language_code)
    if not lines:
        return "", ""
    index = turn % len(lines)
    return lines[index], f"{kind}{index}"
