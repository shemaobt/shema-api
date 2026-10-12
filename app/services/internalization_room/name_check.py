from __future__ import annotations

import json
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


@lru_cache(maxsize=1)
def _forms() -> dict[str, list[str]]:
    forms: dict[str, list[str]] = json.loads(SESSION_FORMS.read_text(encoding="utf-8"))
    return forms


def _keys(element: Element, book: str) -> list[str]:
    entry = registry_entry(book, element.key.rsplit(":", 1)[-1]) or {}
    names = [name.lower() for name in (element.label, entry.get("english") or "") if name]
    return names + [form for name in names for form in _forms().get(name, [])]


def names_heard(coverage_state: dict[str, str], *, team: str, pericope: str) -> dict[str, str]:
    book = load_map(pericope).book
    said = team.lower()
    engaged = [
        element.key
        for element in remaining(coverage_state, pericope)
        if element.kind in _NAMED_KINDS and any(key in said for key in _keys(element, book))
    ]
    return merge(coverage_state, pericope_num=pericope, engaged=engaged)


def hear_the_names(session: IRSession, *, team: str) -> None:
    if is_panorama(session.pericope):
        return
    session.coverage_state = names_heard(
        session.coverage_state or {}, team=team, pericope=session.pericope
    )
