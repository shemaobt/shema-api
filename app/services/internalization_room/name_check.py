from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

from app.core.room_enums import ElementKind
from app.db.models.internalization_room import IRSession
from app.services.internalization_room.canon.elements import Element
from app.services.internalization_room.canon.names import registry_entry
from app.services.internalization_room.canon.parse_map import load_map
from app.services.internalization_room.coverage import is_panorama, merge, remaining

SESSION_FORMS = Path(__file__).parent / "canon" / "session-forms.json"

_NAMED_KINDS = {ElementKind.BEING, ElementKind.PLACE, ElementKind.OBJECT, ElementKind.TIME}

_NOT_A_LETTER = re.compile(r"[^\w\s]|_")
_HEBREW = re.compile("[\u0590-\u05ff]")


@lru_cache(maxsize=1)
def _forms() -> dict[str, list[str]]:
    forms: dict[str, list[str]] = json.loads(SESSION_FORMS.read_text(encoding="utf-8"))
    return forms


def _bare(form: str) -> str:
    return "".join(
        char for char in unicodedata.normalize("NFD", form) if not unicodedata.combining(char)
    )


def _keys(element: Element, book: str) -> list[str]:
    entry = registry_entry(book, element.key.rsplit(":", 1)[-1]) or {}
    english = entry.get("english") or ""
    label = element.label.lower()
    forms = [form.lower() for form in entry.get("referential_forms") or []]
    hebrew = [entry["hebrew_cons"]] if entry.get("hebrew_cons") else []
    if label != english.lower() and label in forms:
        return hebrew
    names = [name.lower() for name in (element.label, english) if name]
    forms_said = [form for name in names for form in _forms().get(name, [])]
    return names + forms_said + [_bare(form) for form in forms_said] + hebrew


def _plain(text: str) -> str:
    return " ".join(_NOT_A_LETTER.sub(" ", unicodedata.normalize("NFC", text.lower())).split())


def _mentions(text: str, keys: list[str]) -> bool:
    padded = f" {_plain(text)} "
    return any(key in text if _HEBREW.search(key) else f" {_plain(key)} " in padded for key in keys)


def names_heard(
    coverage_state: dict[str, str], *, team: str, voice: str, pericope: str
) -> dict[str, str]:
    book = load_map(pericope).book
    named = [
        (element.key, _keys(element, book))
        for element in remaining(coverage_state, pericope)
        if element.kind in _NAMED_KINDS
    ]
    engaged = [key for key, keys in named if _mentions(team, keys)]
    surfaced = [key for key, keys in named if _mentions(voice, keys)]
    return merge(coverage_state, pericope_num=pericope, surfaced=surfaced, engaged=engaged)


def hear_the_names(session: IRSession, *, team: str, voice: str) -> None:
    if is_panorama(session.pericope):
        return
    session.coverage_state = names_heard(
        session.coverage_state or {}, team=team, voice=voice, pericope=session.pericope
    )
