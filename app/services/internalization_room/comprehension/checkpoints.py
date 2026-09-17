"""Deterministic comprehension checkpoints derived from canonical map material.

Checkpoints are not coverage elements and carry no engagement status. They are small
semantic units an assessor may compare with one team answer. Internal codes remain
internal assessment material; the Guide asks a natural oral question without voicing them.

Only a bounded semantic spine blocks readiness — the opening and outcome of each scene,
every significant absence, and every preservation rule — so limited-bridge teams are not
forced through dozens of tiny questions before the recording check and community Refine
stage. Every proposition stays available to the free-retell assessor regardless.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.exceptions import ValidationError
from app.services.internalization_room.canon.book_material import preservation_rules
from app.services.internalization_room.canon.parse_map import MeaningMap, load_map


class Checkpoint(BaseModel):
    id: str
    kind: Literal["proposition", "significant_absence", "preserved_element"]
    critical: bool
    scene_id: str | None = None
    source_id: str
    canonical: dict[str, Any] = Field(default_factory=dict)


def _absence_matches_rule(absence_text: str, kind: str) -> bool:
    """Match a rule against this scene's silence only.

    A multi-scene rule's own wording would make every absence appear related merely
    because the rule mentions its theme globally.
    """
    text = absence_text.lower()
    if "DIVINE_AGENCY" in kind:
        return bool(re.search(r"\bgod\b|yhwh|divine|cause|causation|sent|agent", text))
    if re.search(r"GRIEF|MOURNING|FUNERAL", kind):
        return bool(re.search(r"grief|grieving|mourn|mourning|funeral|lament|wept|weep", text))
    if re.search(r"OFFSPRING|CHILD", kind):
        return bool(re.search(r"child|children|offspring|heir|born|birth", text))
    return False


def semantic_spine_proposition_numbers(meaning_map: MeaningMap) -> set[int]:
    """Opening and outcome preserve each scene's basic movement.

    The vendored parse exposes no per-proposition risk flags, so the spine is exactly the
    first and last proposition of each scene; stable corpus order keeps it deterministic.
    """
    by_scene: dict[int, list[int]] = {}
    for proposition in meaning_map.propositions:
        by_scene.setdefault(proposition.scene, []).append(proposition.number)
    selected: set[int] = set()
    for numbers in by_scene.values():
        if numbers:
            selected.add(numbers[0])
            selected.add(numbers[-1])
    return selected


def derive_checkpoints(meaning_map: MeaningMap, *, book: str) -> list[Checkpoint]:
    pericope = meaning_map.pericope_num
    spine = semantic_spine_proposition_numbers(meaning_map)
    out: list[Checkpoint] = []
    seen: set[str] = set()

    for proposition in meaning_map.propositions:
        source_id = f"P{proposition.number}"
        out.append(
            Checkpoint(
                id=f"proposition:{pericope}:{source_id}",
                kind="proposition",
                critical=proposition.number in spine,
                scene_id=f"S{proposition.scene}",
                source_id=source_id,
                canonical={
                    "ref": proposition.ref,
                    "atoms": [
                        {"q": question, "a": answer} for question, answer in proposition.atoms
                    ],
                },
            )
        )

    structural_rules = [
        rule
        for rule in preservation_rules(book)
        if rule.pericope == pericope and rule.kind.startswith("STRUCTURAL_ABSENCE_")
    ]
    folded_rule_ids: set[str] = set()
    for scene in meaning_map.scenes:
        if not (scene.absence or "").strip():
            continue
        related = [
            rule
            for rule in structural_rules
            if _absence_matches_rule(scene.absence or "", rule.kind)
        ]
        folded_rule_ids.update(rule.rule_id for rule in related)
        out.append(
            Checkpoint(
                id=f"absence:{pericope}:S{scene.number}",
                kind="significant_absence",
                critical=True,
                scene_id=f"S{scene.number}",
                source_id=f"absence:S{scene.number}",
                canonical={
                    "text": scene.absence,
                    "related_audit_ids": [rule.rule_id for rule in related],
                    "related_audit_notes": [rule.note for rule in related],
                },
            )
        )

    for rule in preservation_rules(book):
        if rule.pericope != pericope:
            continue
        if rule.rule_id in folded_rule_ids:
            continue
        out.append(
            Checkpoint(
                id=f"preserved:{pericope}:{rule.rule_id}",
                kind="preserved_element",
                critical=True,
                source_id=rule.rule_id,
                canonical={"audit_kind": rule.kind, "note": rule.note},
            )
        )

    for checkpoint in out:
        if checkpoint.id in seen:
            raise ValidationError(f"Duplicate comprehension checkpoint id: {checkpoint.id}")
        seen.add(checkpoint.id)
    return out


@lru_cache(maxsize=32)
def checkpoints_for(pericope_num: str, book: str = "Ruth") -> tuple[Checkpoint, ...]:
    return tuple(derive_checkpoints(load_map(pericope_num), book=book))


def scene_ids_for(pericope_num: str) -> list[str]:
    return [f"S{scene.number}" for scene in load_map(pericope_num).scenes]


def checkpoint_assessment_material(checkpoint: Checkpoint) -> dict[str, Any]:
    """One checkpoint as the assessor sees it: readiness-only fields stripped, exact
    canonical material and source anchors kept for a grounded comparison."""
    return {
        "checkpoint_id": checkpoint.id,
        "checkpoint_kind": checkpoint.kind,
        "scene_id": checkpoint.scene_id,
        "source_id": checkpoint.source_id,
        "canonical": checkpoint.canonical,
    }
