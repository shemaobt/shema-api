from __future__ import annotations

import enum
import re
from functools import lru_cache

from app.services.internalization_room._default_prompts import fail_safe_utterances
from app.services.internalization_room.languages import FLOOR


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


def utterances(kind: FailSafe, language_code: str = FLOOR) -> list[str]:
    """The pre-approved lines for one situation, in the session language when written.

    These are application strings and not a model call, which is the whole point of a
    fail-safe: nothing generative stands between the failure and what the team hears. The
    H family is the one exception, and it is not a fail-safe — see the supplement.

    The file tags its blocks by primary language (`-pt`) while the room is configured with
    a locale (`pt-BR`), so a regional code is tried and then its primary before falling
    back to the authored English. Without that step every family answers in English for a
    Brazilian team. That was invisible while only the *name* of a line crossed the wire —
    the app held the audio and the indexes match between the two blocks — and it stops
    being invisible the moment a line is synthesized from its text.
    """
    sections = _sections()
    written = localized(kind, language_code)
    if written:
        return written
    return sections.get((str(kind), None), [])


def localized(kind: FailSafe, language_code: str) -> list[str]:
    """The lines written *for this language*, and nothing borrowed from another.

    ``utterances`` never comes back empty, because it falls back to the authored block —
    which is what makes it safe to speak and useless as a measurement. This is the same
    lookup without that fallback, so a guard can ask whether a language the room claims to
    speak has actually had its lines written.

    The untagged authored block counts as the floor's own and not as a borrowing: the file
    says of it *"Written here in English; localize per session language"*, so it is English
    that happens to be untagged rather than English standing in for something unwritten.
    """
    sections = _sections()
    primary = language_code.split("-")[0]
    for tag in (language_code, primary):
        written = sections.get((str(kind), tag))
        if written:
            return written
    if primary == FLOOR:
        return sections.get((str(kind), None), [])
    return []


def first(kind: FailSafe, language_code: str = FLOOR) -> str:
    lines = utterances(kind, language_code)
    return lines[0] if lines else ""


def choose(kind: FailSafe, language_code: str = FLOOR, *, turn: int = 0) -> tuple[str, str]:
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
