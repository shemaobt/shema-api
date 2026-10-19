from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from app.services.internalization_room.canon.book_material import unwalkable
from app.services.internalization_room.canon.parse_map import load_book
from app.services.internalization_room.coverage import PANORAMA_PREFIX
from app.services.internalization_room.languages import AUTHORED

_LINES_FILE = Path(__file__).parent / "prompts" / "passage_lines.md"
_SECTION = re.compile(r"^### ([A-Za-z][A-Za-z0-9]*(?:-[A-Z][A-Za-z]*)?)-([a-z]{2})$", re.M)
_BULLET = re.compile(r'^- "(.+)"$', re.M)

#: The id the wheel once put on the wire for Ruth's Panorama; `resolve_pericope` still reads it.
PANORAMA = "panorama"


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


def line_for(pericope_num: str, language_code: str, *, fallback: str = AUTHORED) -> str:
    """How the room names one passage out loud, or "" when nobody has written it yet.

    An empty line is offered with no sound (ADR 0066).

    The app names a language off a tablet, which may carry a region (`pt-BR`) while the
    lines are authored per language (`pt`), so the region is dropped before looking up.
    Matching the tag whole emptied the entire book in silence, and an empty wheel says
    "everything is done".

    A whole *language* nobody has written falls to the authored English.
    """
    said = _sections()
    for tag in (language_code, language_code.split("-")[0].lower(), fallback):
        spoken = said.get((pericope_num, tag))
        if spoken is not None:
            return spoken
    return ""


def panorama_line_for(book: str, language_code: str) -> str:
    """How the room names one book's Panorama out loud, or "" when it has no line in this
    language yet.

    Unlike ``line_for``, a missing line here never borrows the authored English: the panorama is
    authored in every language at once or voiced in none, so falling back would hand a
    team an answer in the wrong language instead of silence.
    """
    return line_for(PANORAMA_PREFIX + book, language_code, fallback=language_code)


def offered(book: str, spoken: str) -> list[tuple[str, str]]:
    return [
        (meaning_map.pericope_num, line_for(meaning_map.pericope_num, spoken))
        for meaning_map in load_book(book)
        if not unwalkable(meaning_map)
    ]
