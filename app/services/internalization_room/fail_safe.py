from __future__ import annotations

import enum
import re
from functools import lru_cache
from typing import Any, Literal

from app.services.internalization_room._default_prompts import fail_safe_utterances
from app.services.internalization_room.languages import FLOOR


class FailSafe(enum.StrEnum):
    UNREPAIRABLE = "A"
    OUTSIDE_MAP = "B"
    HANDOFF = "C"
    INAUDIBLE = "D"
    HARD_STOP = "E"
    INSTANT_ACK = "F"
    #: Only from `turn/speech.py`'s own detection over the team's audio, at 0.98 confidence
    #: over substantial speech. A Guide draft that strays from the bridge language is a
    #: draft failure and takes `UNREPAIRABLE` instead — telling the team they rehearsed in
    #: their own tongue when the model, not them, left the session's language.
    OFF_BRIDGE_LANGUAGE = "G"
    UNTOLD_STRETCH = "H"
    STRETCH_TO_CORRECT = "I"


ProcessFamily = Literal["P", "X"]

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


def utterances(kind: FailSafe | ProcessFamily, language_code: str = FLOOR) -> list[str]:
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


def localized(kind: FailSafe | ProcessFamily, language_code: str) -> list[str]:
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

    It takes a ``FailSafe`` and never a process family, so that a step cannot be handed to
    the one reader that rotates: ``choose("X", turn=7)`` would answer X-whole where the step
    means the retelling, and the type is what refuses it. The lookup underneath is closed to
    the same two sets, so the refusal does not end here and turn into silence one call down.
    """
    lines = utterances(kind, language_code)
    if not lines:
        return "", ""
    index = turn % len(lines)
    return lines[index], f"{kind}{index}"


def inaudible_ladder(messages: list[dict[str, Any]], language_code: str) -> tuple[str, str]:
    """The D line for one more miss, read off how many the room is already answering.

    The ladder used to be indexed by the length of the conversation, so the very first miss
    could draw the third line and a team heard perfectly for twenty turns met whichever line
    the count landed on. It walks the run of misses now — the trailing guide turns that
    answered with a D line — and any turn the room did hear starts it over.

    It stays on the last line rather than wrapping: a fourth miss re-opening with the first
    line would ask again as if for the first time, and her rule is one D per evidence asked.
    """
    misses = 0
    for message in reversed(messages):
        if message.get("role") != "guide":
            continue
        if message.get("category") != str(FailSafe.INAUDIBLE):
            break
        misses += 1
    last = len(utterances(FailSafe.INAUDIBLE, language_code)) - 1
    return choose(FailSafe.INAUDIBLE, language_code, turn=min(misses, last))


class UnknownProcessLine(LookupError):
    """A process line was asked for by a family or a step nobody wrote.

    Every other lookup in this module answers a miss with ``""`` or ``[]``, because a
    fail-safe that cannot find its block is better silent than wrong — the team is already
    meeting a failure and a wrong sentence would make it worse. A process step is the
    opposite case: the caller is the app walking its own steps, so a name that is not in
    the tables is a bug of ours, and a step served as silence would stall a screen with no
    trace of why. It is a ``LookupError`` and not one of the errors in ``app.core``: those
    are registered to become a status code, and a step nobody wrote must not reach a team
    standing in a room as a 404 about their own session.
    """


PROCESS_STEPS: dict[ProcessFamily, tuple[str, ...]] = {
    "P": ("start", "tell", "unheard", "approved"),
    "X": ("open", "retell", "whole", "frases", "thanks"),
}


def process_line(family: ProcessFamily, step: str, language_code: str = FLOOR) -> tuple[str, str]:
    """The line for one step of the telling-back or of the external check, and its name.

    A fail-safe answers a failure and rotates, on the authored file's own instruction. A
    process line marks a step, and her prose says of both families that *"the order is
    fixed and read by position"*: rotating them would voice the thanks where the step means
    the invitation. So there is no ``turn`` here, and the same step always answers the same.

    The language resolution is ``choose``'s, unchanged — regional, then primary, then the
    authored English — and so is the shape of the answer, because the two consumers want
    different halves of it: a step spoken by the server needs the text, and a step played
    from the app's bundle needs the name.
    """
    steps = PROCESS_STEPS.get(family)
    if steps is None or step not in steps:
        raise UnknownProcessLine(f"no process line is written for {family!r} step {step!r}")
    position = steps.index(step)
    lines = utterances(family, language_code)
    if position >= len(lines):
        raise UnknownProcessLine(
            f"family {family!r} has no line at position {position} in {language_code!r}"
        )
    return lines[position], f"{family}{position}"
