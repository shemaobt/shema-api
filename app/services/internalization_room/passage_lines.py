from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from app.services.internalization_room.languages import FLOOR

_LINES_FILE = Path(__file__).parent / "prompts" / "passage_lines.md"
_SECTION = re.compile(r"^### ([A-Z]\d+)-([a-z]{2})$", re.M)
_BULLET = re.compile(r'^- "(.+)"$', re.M)


@lru_cache(maxsize=1)
def _sections() -> dict[tuple[str, str], str]:
    text = _LINES_FILE.read_text(encoding="utf-8")
    marks = list(_SECTION.finditer(text))
    parsed: dict[tuple[str, str], str] = {}
    for index, mark in enumerate(marks):
        end = marks[index + 1].start() if index + 1 < len(marks) else len(text)
        said = _BULLET.findall(text[mark.end() : end])
        if said:
            parsed[(mark.group(1), mark.group(2))] = said[0]
    return parsed


def line_for(pericope_num: str, language_code: str, *, floor: str = FLOOR) -> str:
    """How the room names one passage out loud, or "" when nobody has written it yet.

    An empty line is not an error the team should meet: a passage the room cannot name is
    a passage it must not offer, so the caller drops it from the wheel rather than reading
    a number aloud or falling silent on a tap.

    The app names a language off a tablet, which may carry a region (`pt-BR`) while the
    lines are authored per language (`pt`), so the region is dropped before looking up.
    Matching the tag whole emptied the entire book in silence, and an empty wheel says
    "everything is done".

    A whole *language* nobody has written falls to the floor rather than emptying the book.
    One unnamed passage is a passage withheld, which is the deliberate behaviour above; every
    passage unnamed at once is a room telling a team it has finished a book it never opened,
    and that is a different thing entirely.
    """
    said = _sections()
    for tag in (language_code, language_code.split("-")[0].lower(), floor):
        spoken = said.get((pericope_num, tag))
        if spoken is not None:
            return spoken
    return ""
