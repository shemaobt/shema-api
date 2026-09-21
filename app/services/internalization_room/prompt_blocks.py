from __future__ import annotations

from app.services.internalization_room.canon.book_material import (
    preservation_rules,
    story_so_far,
)
from app.services.internalization_room.canon.elements import (
    Element,
    ElementKind,
    elements_for,
)
from app.services.internalization_room.canon.parse_map import load_map
from app.services.internalization_room.coverage import (
    CoverageStatus,
    current_scene,
    initial_state,
    remaining,
)


def _short_label(element: Element, scenes: dict[int, str]) -> str:
    """A label the Guide can say: a scene by its verses, a silence by its scene, a rule by
    its number, and everything else by the map's own line for it — in the scene it is in,
    because the team saying "Naomi" in scene 1 does not answer for her in scene 3."""
    if element.kind is ElementKind.SCENE and element.scene is not None:
        return scenes[element.scene]
    if element.kind is ElementKind.ABSENCE:
        return f"absence @ S{element.scene}"
    if element.kind is ElementKind.PRESERVED and element.rule_id is not None:
        return element.rule_id
    if element.scene is not None:
        return f"{element.label} @ S{element.scene}"
    return element.label


def coverage_status_block(coverage_state: dict[str, str], pericope_num: str) -> str:
    """Her three parts, in her order: the scene, what is behind the team, what is not.

    Information only (DOCTRINE §2.1): the block says where the ledger last saw the team
    and what they have and have not worked; it never says what to do next. No key and no
    audit kind reaches it — the Guide speaks names, never codes, and it has no screen to
    check a code against.
    """
    scenes = {
        scene.number: f"S{scene.number} ({scene.verses})" for scene in load_map(pericope_num).scenes
    }
    merged = {**initial_state(pericope_num), **coverage_state}
    covered = [
        _short_label(element, scenes)
        for element in elements_for(pericope_num)
        if merged.get(element.key) == CoverageStatus.ENGAGED
    ]
    scene = current_scene(coverage_state, pericope_num)
    if scene is not None:
        scene_line = f"CURRENT SCENE: {scene}"
    elif all(
        merged.get(element.key) == CoverageStatus.ENGAGED
        for element in elements_for(pericope_num)
        if element.scene is not None
    ):
        scene_line = (
            "CURRENT SCENE: (whole-passage integration — every scene has been engaged; "
            "check the remaining whole-passage meaning and the team's readiness)"
        )
    else:
        scene_line = (
            "CURRENT SCENE: (whole-passage opening — help the team feel the shape before "
            "any one scene)"
        )
    covered_line = "COVERED (engaged): " + (
        "; ".join(covered) if covered else "(nothing engaged yet — the session is just beginning)"
    )
    left = remaining(coverage_state, pericope_num)
    if not left:
        remaining_lines = ["REMAINING: (none — every element has been worked by the team)"]
    else:
        by_kind: dict[ElementKind, list[str]] = {}
        for element in left:
            by_kind.setdefault(element.kind, []).append(_short_label(element, scenes))
        remaining_lines = ["REMAINING (not yet worked by the team, in their own words):"]
        remaining_lines.extend(
            f"  {kind}: {', '.join(by_kind[kind])}" for kind in ElementKind if kind in by_kind
        )
    return "\n".join([scene_line, "", covered_line, "", *remaining_lines])


def meaning_map_block(pericope_num: str, book: str) -> str:
    """The passage's map verbatim, plus the digests of strictly earlier passages.

    *Tripod Internalization · Interaction Flows*
    (`internalization-room/docs/spec/interaction-flows.md`, §1, diagram caption) calls the
    Guide's standard of truth "MEANING MAP + story-so-far", and the earlier-only scoping is
    what keeps a later disclosure from reaching this session.
    """
    passage = load_map(pericope_num).body
    earlier = story_so_far(book, pericope_num)
    return f"{passage}\n\n{earlier}" if earlier else passage


def validator_map_block(pericope_num: str, book: str) -> str:
    """The Guide's map plus the prohibitions the Guide is never shown, and the story so far.

    The two roles read the same passage and judge it against different things. Ported from
    the project's own `validatorMapText` (`Tripod-Internalization`, `src/turn/mapText.ts:85`),
    whose framing sentence is reproduced verbatim because it is what tells the Validator that
    a plausible-sounding draft is still ungrounded when it crosses one of these.

    Until now `standard_of_truth` was the Guide's own map, so the withholdings the project
    wrote down — R10, which forbids pairing the wives with their husbands before Ruth 4:10 —
    reached the coverage beads and stopped there. A draft that picked one of the two pairings
    contradicted nothing the Validator had been given.
    """
    meaning_map = load_map(pericope_num)
    rules = "\n".join(
        rule.render() for rule in preservation_rules(book) if rule.pericope == pericope_num
    )
    absences = "\n".join(
        f"- S{scene.number} ({scene.verses}): {scene.absence}"
        for scene in meaning_map.scenes
        if scene.absence
    )
    validator_map = (
        f"{meaning_map.body}\n\n---\n\n"
        "## PRESERVATION RULES — do_not_decide (HARD CONSTRAINTS)\n"
        "These are explicit prohibitions from the Compilation Log. The response must honor "
        "every one; a draft that violates any of these is ungrounded even if it sounds "
        f"plausible.\n\n{rules}\n\n"
        "## SIGNIFICANT ABSENCES (per scene — silences that must be preserved, never "
        f"filled)\n\n{absences}\n"
    )
    earlier = story_so_far(book, pericope_num)
    return f"{validator_map}\n\n{earlier}" if earlier else validator_map
