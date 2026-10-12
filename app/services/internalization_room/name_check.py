from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.room_enums import ElementKind
from app.db.models.internalization_room import IRSession
from app.services.internalization_room.canon.elements import Element, elements_for
from app.services.internalization_room.canon.names import (
    WITHHELD_BEING_LABEL,
    registry_entry,
    roles_in_scene,
)
from app.services.internalization_room.canon.parse_map import load_map
from app.services.internalization_room.coverage import is_panorama, merge, remaining
from app.services.internalization_room.coverage_events import record_transitions

SESSION_FORMS = Path(__file__).parent / "canon" / "session-forms.json"

_UNNAMED_HERE = " (unnamed here)"
_NAMED_KINDS = {ElementKind.BEING, ElementKind.PLACE, ElementKind.OBJECT, ElementKind.TIME}

_NOT_A_LETTER = re.compile(r"[^\w\s]|_")
_NOT_A_NAME_LETTER = re.compile(r"[^\w'\s]|_")
_NOT_A_WORD_LETTER = re.compile(r"[\W_]")
_PROPER_NOUN = re.compile(r"^[A-Z][^\W\d_]{3,}$")
_STOP = {
    "the",
    "of",
    "in",
    "and",
    "a",
    "an",
    "to",
    "at",
    "on",
    "by",
    "for",
    "with",
    "his",
    "her",
    "their",
    "its",
    "one",
    "each",
    "own",
}
_GENERIC = {
    "fields",
    "field",
    "land",
    "days",
    "women",
    "woman",
    "house",
    "sons",
    "about",
    "their",
    "after",
    "before",
    "until",
    "when",
    "where",
    "with",
    "from",
    "into",
    "whole",
    "went",
}
_HEBREW = re.compile("[\u0590-\u05ff]")


@lru_cache(maxsize=1)
def _forms() -> dict[str, list[str]]:
    forms: dict[str, list[str]] = json.loads(SESSION_FORMS.read_text(encoding="utf-8"))
    return forms


def _bare(form: str) -> str:
    return "".join(
        char for char in unicodedata.normalize("NFD", form) if not unicodedata.combining(char)
    )


def _name_plain(name: str) -> str:
    return " ".join(_NOT_A_NAME_LETTER.sub(" ", unicodedata.normalize("NFC", name.lower())).split())


def _content_words(name: str) -> list[str]:
    return [word for word in _name_plain(name).split(" ") if len(word) >= 3 and word not in _STOP]


def _word_said(word: str) -> list[str]:
    return _forms().get(word, []) + _forms().get(word.removesuffix("'s"), [])


def _whole_forms(name: str) -> list[str]:
    words = _content_words(name)
    single = _word_said(words[0]) if len(words) == 1 else []
    return _with_bare(_forms().get(_name_plain(name), []) + single)


def _word_forms(name: str) -> list[str]:
    words = _content_words(name)
    return _with_bare([form for word in words if len(words) > 1 for form in _word_said(word)])


def _code(element: Element) -> str:
    return element.key.rsplit(":", 1)[-1]


def _with_bare(forms: list[str]) -> list[str]:
    return forms + [_bare(form) for form in forms]


def _own_names(book: str, code: str) -> set[str]:
    entry = registry_entry(book, code) or {}
    english = entry.get("english") or ""
    if entry.get("kind") != "PERSON" or not english:
        return set()
    single = _content_words(english)[:1] if len(_content_words(english)) == 1 else []
    return {_plain(name) for name in [english, *single, *_whole_forms(english)]}


def _carried(book: str, peer: Element, role: str) -> set[str]:
    english = (registry_entry(book, _code(peer)) or {}).get("english") or ""
    texts = [text for text in (peer.label, role.replace("_", " "), english) if text]
    return {
        _plain(word)
        for text in texts
        for word in _content_words(text) + _whole_forms(text) + _word_forms(text)
    }


def _keys(element: Element, book: str, elements: tuple[Element, ...], pericope: str) -> list[str]:
    if element.label == WITHHELD_BEING_LABEL:
        return [element.label]
    beings = {_code(other) for other in elements if other.kind is ElementKind.BEING}
    entry = registry_entry(book, _code(element)) or {}
    english = entry.get("english") or ""
    shown = element.label.removesuffix(_UNNAMED_HERE)
    label = shown.lower()
    forms = [form.lower() for form in entry.get("referential_forms") or []]
    hebrew = [entry["hebrew_cons"]] if entry.get("hebrew_cons") else []
    if label != english.lower() and label in forms:
        return hebrew
    names = [name.lower() for name in (shown, english) if name]
    tokens = [
        word
        for word in english.split()
        if _PROPER_NOUN.match(word) and word.lower() not in _GENERIC
    ]
    if not entry:
        words = [_NOT_A_WORD_LETTER.sub("", word.lower()) for word in shown.split()]
        tokens += [word for word in words if len(word) >= 5 and word not in _GENERIC]
    whole = names + [form for name in names for form in _whole_forms(name)] + hebrew
    whole += entry.get("referential_forms") or []
    parts = [form for name in names for form in _word_forms(name)] + tokens
    taken = set().union(*(_own_names(book, other) for other in beings - {_code(element)}))
    if entry.get("kind") == "PERSON" and element.scene is not None:
        roles = roles_in_scene(pericope, element.scene)
        taken |= set().union(
            *(
                _carried(book, peer, roles.get(_code(peer), ""))
                for peer in elements
                if peer.kind is ElementKind.BEING
                and peer.scene == element.scene
                and _code(peer) != _code(element)
            )
        )
    return whole + [part for part in parts if _plain(part) not in taken]


def _plain(text: str) -> str:
    return " ".join(_NOT_A_LETTER.sub(" ", unicodedata.normalize("NFC", text.lower())).split())


def _mentions(text: str, keys: list[str]) -> bool:
    padded = f" {_plain(text)} "
    return any(key in text if _HEBREW.search(key) else f" {_plain(key)} " in padded for key in keys)


def names_heard(
    coverage_state: dict[str, str], *, team: str, voice: str, pericope: str
) -> dict[str, str]:
    book = load_map(pericope).book
    elements = elements_for(pericope)
    named = [
        (element.key, _keys(element, book, elements, pericope))
        for element in remaining(coverage_state, pericope)
        if element.kind in _NAMED_KINDS
    ]
    engaged = [key for key, keys in named if _mentions(team, keys)]
    surfaced = [key for key, keys in named if _mentions(voice, keys)]
    return merge(coverage_state, pericope_num=pericope, surfaced=surfaced, engaged=engaged)


def stored_opening_note(session: IRSession) -> str:
    return next(
        (str(entry["text"]) for entry in session.messages or [] if entry.get("opening_note")), ""
    )


def hear_the_names(db: AsyncSession, session: IRSession, *, team: str, voice: str) -> None:
    if is_panorama(session.pericope):
        return
    before = session.coverage_state or {}
    after = names_heard(before, team=team, voice=voice, pericope=session.pericope)
    record_transitions(db, session, before=before, after=after)
    session.coverage_state = after
