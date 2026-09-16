from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

from pydantic import BaseModel

#: Re-exported so a reader of `elements_of` sees the values it builds on without leaving
#: the file. It is defined in `core` because `app/models` needs it too, and a DTO module
#: importing this package would run its `__init__` and close an import cycle.
from app.core.room_enums import ElementKind
from app.services.internalization_room.canon.book_material import (
    PreservationRule,
    preservation_rules,
)
from app.services.internalization_room.canon.parse_map import Entity, MeaningMap, load_map


class Element(BaseModel):
    key: str
    label: str
    kind: ElementKind
    scene: int | None = None
    detail: str = ""


_AXES = (
    (ElementKind.ARC, "arc_prose"),
    (ElementKind.CONTEXT, "context_prose"),
    (ElementKind.TONE, "tone_prose"),
    (ElementKind.FUNCTION, "function_prose"),
)


def _slug(text: str) -> str:
    """Key an unlinked entity by its name alone.

    Parentheticals are dropped on purpose: the same road is written `the road (implied;
    continues from P02)` in one scene and `the road (continued)` in the next, and keying on the
    whole line would put two beads on the necklace for one place.
    """
    without_notes = re.sub(r"\([^)]*\)", " ", text)
    plain = unicodedata.normalize("NFKD", without_notes).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", plain.casefold()).strip("-")[:32] or "unnamed"


@lru_cache(maxsize=64)
def scene_of(pericope_num: str, book: str = "Ruth") -> dict[str, int]:
    """The scene each bead belongs to, for every bead that belongs to one.

    Preservation rules and the Level-1 axes are absent: they belong to the passage and to
    none of its scenes.
    """
    return {
        element.key: element.scene
        for element in elements_for(pericope_num, book)
        if element.scene is not None
    }


def scene_key(number: int) -> str:
    """A scene's own bead, named. The one place the shape of that key is written.

    It was an f-string inside `elements_of` and nowhere else, which was fine while the number
    alone never left this side. The coverage route now says which scene a bead sits in by
    naming that scene's bead, so the format has a second reader — and a format with two
    readers and one spelling is a format that drifts the moment either moves.
    """
    return f"{ElementKind.SCENE}:{number}"


def _entity_key(kind: ElementKind, scene_number: int, entity: Entity) -> str:
    """Stable across sessions: coverage is persisted under these keys."""
    return f"{kind}:S{scene_number}:{entity.code or _slug(_label(entity))}"


def _label(entity: Entity) -> str:
    """The human-readable tail of `[[B3-Naomi]] — נָעֳמִי / Naomi`."""
    after_link = entity.label.split("]]", 1)[-1].lstrip(" —-")
    return (after_link or entity.label).strip()


def elements_of(meaning_map: MeaningMap, *, book: str | None = None) -> list[Element]:
    """The passage's coverage spine, derived from its map.

    The four Level-1 axes first, then one bead per scene, per entity in each scene, per
    significant absence, and per preserved element. An entity is a bead in every scene it
    appears in, labelled with that scene's own line: Naomi in scene 4 of Ruth 1 is "the
    woman", and the team saying "Naomi" in scene 1 does not answer for her there. A
    preservation rule about the same silence as a scene's absence rides on that absence
    bead — the teaching prose and the hard constraint are one thing to notice, not two —
    and only the rules that fold into no scene keep a bead of their own.

    Level 3 is deliberately not used here. Its atoms are the payload for verification; making
    them the conversation's spine would turn a session into a forty-item interrogation.
    """
    elements: list[Element] = [
        Element(
            key=kind.value,
            label=f"Level-1 {kind.value}",
            kind=kind,
            detail=" ".join(getattr(meaning_map, section).split()),
        )
        for kind, section in _AXES
    ]

    rules = (
        [rule for rule in preservation_rules(book) if rule.pericope == meaning_map.pericope_num]
        if book
        else []
    )
    folded: set[str] = set()

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
                elements.append(
                    Element(
                        key=_entity_key(kind, scene.number, entity),
                        label=_label(entity),
                        kind=kind,
                        scene=scene.number,
                    )
                )
        if scene.absence:
            related = [rule for rule in rules if rule.folds_into(scene.absence)]
            folded.update(rule.rule_id for rule in related)
            elements.append(
                Element(
                    key=f"{ElementKind.ABSENCE}:{scene.number}",
                    label=" — ".join([scene.absence, *(_rule_label(rule) for rule in related)]),
                    kind=ElementKind.ABSENCE,
                    scene=scene.number,
                )
            )

    for rule in rules:
        if rule.rule_id in folded:
            continue
        elements.append(
            Element(
                key=f"{ElementKind.PRESERVED}:{rule.rule_id}",
                label=_rule_label(rule),
                kind=ElementKind.PRESERVED,
            )
        )
    return elements


def _rule_label(rule: PreservationRule) -> str:
    return f"{rule.kind}: {rule.note}"


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
