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
from app.services.internalization_room.classify_coverage import _shown_status
from app.services.internalization_room.coverage import CoverageStatus


def _short_label(element: Element, scenes: dict[int, str]) -> str:
    """A label the Guide can say: a scene by its verses, a silence by its scene, a rule by
    its number, and everything else by the map's own line for it."""
    if element.kind is ElementKind.SCENE and element.scene is not None:
        return scenes[element.scene]
    if element.kind is ElementKind.ABSENCE:
        return f"absence @ S{element.scene}"
    if element.kind is ElementKind.PRESERVED and element.rule_id is not None:
        return element.rule_id
    return element.label


_HER_KIND_NAMES = {
    ElementKind.ABSENCE: "significant_absence",
    ElementKind.PRESERVED: "preserved_element",
}


def _by_kind(elements: list[Element], scenes: dict[int, str]) -> list[str]:
    by_kind: dict[ElementKind, list[str]] = {}
    for element in elements:
        by_kind.setdefault(element.kind, []).append(_short_label(element, scenes))
    return [
        f"  {_HER_KIND_NAMES.get(kind, kind.value)}: {', '.join(dict.fromkeys(by_kind[kind]))}"
        for kind in ElementKind
        if kind in by_kind
    ]


def coverage_status_block(
    coverage_state: dict[str, str], pericope_num: str, current_scene: str | None = None
) -> str:
    """Her LEDGER (`src/turn/coverageStatus.ts:18-56`): what the team worked, what the Guide
    raised and the team has not taken up, and what nobody has touched yet.

    Information only (DOCTRINE §2.1): it never says what to do next. No key and no audit
    kind reaches it — the Guide speaks names, never codes, and it has no screen to check a
    code against.
    """
    scenes = {
        scene.number: f"S{scene.number} ({scene.verses})" for scene in load_map(pericope_num).scenes
    }
    elements = elements_for(pericope_num)
    status = {element.key: _shown_status(coverage_state, element) for element in elements}
    engaged = [e for e in elements if status[e.key] == CoverageStatus.ENGAGED]
    surfaced = [e for e in elements if status[e.key] == CoverageStatus.SURFACED]
    untouched = [e for e in elements if e not in engaged and e not in surfaced]
    worked = (
        "; ".join(dict.fromkeys(_short_label(element, scenes) for element in engaged))
        if engaged
        else "(nothing yet — the session is just beginning)"
    )
    return "\n".join(
        [
            "LEDGER (the app's notes — information only; you decide what comes next)",
            *([f"SCENE THE LEDGER LAST SAW THE TEAM IN: {current_scene}"] if current_scene else []),
            "",
            f"WORKED WITH BY THE TEAM (engaged): {worked}",
            "",
            *(
                ["RAISED BY YOU, NOT YET TAKEN UP BY THE TEAM:", *_by_kind(surfaced, scenes), ""]
                if surfaced
                else []
            ),
            "NOT YET TOUCHED (still deserve a visit before the session ends):",
            *(
                _by_kind(untouched, scenes)
                if untouched
                else ["  (nothing — everything in the map has been visited)"]
            ),
        ]
    )


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
