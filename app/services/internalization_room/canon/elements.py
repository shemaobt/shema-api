from __future__ import annotations

import enum
import re
import unicodedata
from functools import lru_cache

from pydantic import BaseModel

from app.services.internalization_room.canon.book_material import preservation_rules
from app.services.internalization_room.canon.parse_map import Entity, MeaningMap, load_map


class ElementKind(enum.StrEnum):
    SCENE = "scene"
    BEING = "being"
    PLACE = "place"
    OBJECT = "object"
    TIME = "time"
    ABSENCE = "absence"
    PRESERVED = "preserved"


class Element(BaseModel):
    key: str
    label: str
    kind: ElementKind
    scene: int | None = None


def _slug(text: str) -> str:
    """Key an unlinked entity by its name alone.

    Parentheticals are dropped on purpose: the same road is written `the road (implied;
    continues from P02)` in one scene and `the road (continued)` in the next, and keying on the
    whole line would put two beads on the necklace for one place.
    """
    without_notes = re.sub(r"\([^)]*\)", " ", text)
    plain = unicodedata.normalize("NFKD", without_notes).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", plain.casefold()).strip("-")[:32] or "unnamed"


def scene_key(number: int) -> str:
    """A scene's own bead, named. The one place the shape of that key is written.

    It was an f-string inside `elements_of` and nowhere else, which was fine while the number
    alone never left this side. The coverage route now says which scene a bead sits in by
    naming that scene's bead, so the format has a second reader — and a format with two
    readers and one spelling is a format that drifts the moment either moves.
    """
    return f"{ElementKind.SCENE}:{number}"


def _entity_key(kind: ElementKind, entity: Entity) -> str:
    """Stable across sessions: coverage is persisted under these keys."""
    return f"{kind}:{entity.code or _slug(_label(entity))}"


def _label(entity: Entity) -> str:
    """The human-readable tail of `[[B3-Naomi]] — נָעֳמִי / Naomi`."""
    after_link = entity.label.split("]]", 1)[-1].lstrip(" —-")
    return (after_link or entity.label).strip()


def elements_of(meaning_map: MeaningMap, *, book: str | None = None) -> list[Element]:
    """The passage's coverage spine, derived from its map.

    One bead per scene, per distinct entity, per significant absence, and per preserved
    element — which is the completion floor the design document names. Entities are deduped
    across the passage on purpose: Naomi appearing in three scenes is one thing for the team
    to work with, not three.

    Level 3 is deliberately not used here. Its atoms are the payload for verification; making
    them the conversation's spine would turn a session into a forty-item interrogation.
    """
    elements: list[Element] = []
    seen: set[str] = set()

    for scene in meaning_map.scenes:
        elements.append(
            Element(
                key=scene_key(scene.number),
                label=scene.title,
                kind=ElementKind.SCENE,
                scene=scene.number,
            )
        )
        groups = (
            (ElementKind.BEING, scene.beings),
            (ElementKind.PLACE, scene.places),
            (ElementKind.OBJECT, scene.objects),
            (ElementKind.TIME, scene.times),
        )
        for kind, entities in groups:
            for entity in entities:
                key = _entity_key(kind, entity)
                if key in seen:
                    continue
                seen.add(key)
                elements.append(
                    Element(key=key, label=_label(entity), kind=kind, scene=scene.number)
                )
        if scene.absence:
            elements.append(
                Element(
                    key=f"{ElementKind.ABSENCE}:{scene.number}",
                    label=scene.absence,
                    kind=ElementKind.ABSENCE,
                    scene=scene.number,
                )
            )

    if book:
        for rule in preservation_rules(book):
            if rule.pericope != meaning_map.pericope_num:
                continue
            elements.append(
                Element(
                    key=f"{ElementKind.PRESERVED}:{rule.rule_id}",
                    label=f"{rule.kind}: {rule.note}",
                    kind=ElementKind.PRESERVED,
                )
            )
    return elements


@lru_cache(maxsize=32)
def elements_for(pericope_num: str, book: str = "Ruth") -> tuple[Element, ...]:
    return tuple(elements_of(load_map(pericope_num), book=book))


def element_keys(pericope_num: str, book: str = "Ruth") -> list[str]:
    return [element.key for element in elements_for(pericope_num, book)]


def absence_index(pericope_num: str, book: str = "Ruth") -> int:
    """Where the first significant absence sits in bead order, for the ring bead."""
    for index, element in enumerate(elements_for(pericope_num, book)):
        if element.kind is ElementKind.ABSENCE:
            return index
    return -1
