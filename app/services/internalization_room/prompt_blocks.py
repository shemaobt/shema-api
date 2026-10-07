from __future__ import annotations

from enum import Enum, auto

from app.core.room_enums import EarlierPassageStatus
from app.services.internalization_room.canon.book_material import (
    preservation_rules,
    significant_absences,
    story_so_far,
)
from app.services.internalization_room.canon.elements import (
    Element,
    ElementKind,
    elements_for,
)
from app.services.internalization_room.canon.parse_map import (
    MeaningMap,
    code_only_links,
    load_book,
    load_map,
)
from app.services.internalization_room.coverage import (
    CoverageStatus,
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


_LEDGER = "LEDGER (the app's notes — information only; you decide what comes next)"

_HER_KIND_NAMES = {
    ElementKind.ABSENCE: "significant_absence",
    ElementKind.PRESERVED: "preserved_element",
}


def coverage_status_block(coverage_state: dict[str, str], pericope_num: str) -> str:
    """Her ledger (`src/turn/coverageStatus.ts`, app 18fa7c4): what the team has and has not
    worked, and no line pointing at a scene. No key and no audit kind reaches it."""
    scenes = {
        scene.number: f"S{scene.number} ({scene.verses})" for scene in load_map(pericope_num).scenes
    }
    merged = {**initial_state(pericope_num), **coverage_state}
    covered = [
        _short_label(element, scenes)
        for element in elements_for(pericope_num)
        if merged.get(element.key) == CoverageStatus.ENGAGED
    ]
    covered_line = "WORKED WITH BY THE TEAM (engaged): " + (
        "; ".join(covered) if covered else "(nothing yet — the session is just beginning)"
    )
    left = remaining(coverage_state, pericope_num)
    if not left:
        remaining_lines = ["REMAINING: (none — every element has been worked by the team)"]
    else:
        by_kind: dict[ElementKind, list[str]] = {}
        for element in left:
            by_kind.setdefault(element.kind, []).append(_short_label(element, scenes))
        remaining_lines = ["NOT YET TOUCHED (still deserve a visit before the session ends):"]
        remaining_lines.extend(
            f"  {_HER_KIND_NAMES.get(kind, kind)}: {', '.join(by_kind[kind])}"
            for kind in ElementKind
            if kind in by_kind
        )
    return "\n".join([_LEDGER, "", covered_line, "", *remaining_lines])


_EARLIER_GROUPS = (
    (EarlierPassageStatus.APPROVED, "Approved"),
    (EarlierPassageStatus.STARTED, "Started, not approved yet"),
    (EarlierPassageStatus.NOT_WORKED, "Not worked yet"),
)


def earlier_passages_line(pericope_num: str, book: str, statuses: dict[str, str] | None) -> str:
    """Her EARLIER PASSAGES FOR THIS TEAM fact, verbatim (`src/turn/earlierPassages.ts`).

    Each passage is named by the reference that heads its digest in THE STORY SO FAR. The fact
    is complete or absent: a status missing for any earlier passage of the book renders no
    line at all, as her app renders none, so a partial stamp never claims the rest unworked.
    """
    stamped = _stamped_earlier(pericope_num, book, statuses)
    if not stamped:
        return ""
    groups = [
        f"{label}: {', '.join(m.reference for m, given in stamped if given == status)}."
        for status, label in _EARLIER_GROUPS
        if any(given == status for _, given in stamped)
    ]
    return f"EARLIER PASSAGES FOR THIS TEAM: {' '.join(groups)}"


class RoomFact(Enum):
    """The facts after the ledger, in the order of her `liveTurn.ts:447-503` (app 18fa7c4)."""

    SCENE_REHEARSALS = auto()
    KEPT_REHEARSALS = auto()
    EARLIER_PASSAGES = auto()
    MOMENT = auto()
    ACCEPTED_READINGS = auto()


def room_facts_block(facts: dict[RoomFact, str]) -> str:
    return "\n\n".join(facts[fact] for fact in RoomFact if facts.get(fact))


def _stamped_earlier(
    pericope_num: str, book: str, statuses: dict[str, str] | None
) -> list[tuple[MeaningMap, str]]:
    earlier = [m for m in load_book(book) if m.pericope_num < pericope_num]
    if not statuses or any(m.pericope_num not in statuses for m in earlier):
        return []
    return [(m, statuses[m.pericope_num]) for m in earlier]


def _not_worked(pericope_num: str, book: str, statuses: dict[str, str] | None) -> frozenset[str]:
    return frozenset(
        m.pericope_num
        for m, status in _stamped_earlier(pericope_num, book, statuses)
        if status == EarlierPassageStatus.NOT_WORKED
    )


def meaning_map_block(
    pericope_num: str, book: str, earlier_passages: dict[str, str] | None = None
) -> str:
    """The passage's map with its links as codes alone, plus the earlier passages' digests.

    *Tripod Internalization · Interaction Flows*
    (`internalization-room/docs/spec/interaction-flows.md`, §1, diagram caption) calls the
    Guide's standard of truth "MEANING MAP + story-so-far", and the earlier-only scoping is
    what keeps a later disclosure from reaching this session.
    """
    passage = code_only_links(load_map(pericope_num).body)
    earlier = story_so_far(book, pericope_num, _not_worked(pericope_num, book, earlier_passages))
    return f"{passage}\n\n{earlier}" if earlier else passage


def validator_map_block(
    pericope_num: str, book: str, earlier_passages: dict[str, str] | None = None
) -> str:
    """The passage's map plus the rules and silences the Guide is never shown, and the story so far.

    The live turn's Guide and Validator read her notices for the session's stamp. The Ensaio
    Final's readers and the golden judge read the map with no notice, as her `ctx.validatorMap`
    is read, so in a stamped session with an unworked passage the verdict's prefix differs from
    the live Validator's and is cached on its own. Ported from
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
        rule.render(tagged=False)
        for rule in preservation_rules(book)
        if rule.pericope == pericope_num
    )
    absences = "\n".join(
        f"- {absence.scene_id} ({absence.verse_range}): {absence.text}"
        for absence in significant_absences(pericope_num)
    )
    validator_map = code_only_links(
        f"{meaning_map.body}\n\n---\n\n"
        "## PRESERVATION RULES — do_not_decide (HARD CONSTRAINTS)\n"
        "These are explicit prohibitions from the Compilation Log. The response must honor "
        "every one; a draft that violates any of these is ungrounded even if it sounds "
        f"plausible.\n\n{rules}\n\n"
        "## SIGNIFICANT ABSENCES (per scene — silences that must be preserved, never "
        f"filled)\n\n{absences}\n"
    )
    earlier = story_so_far(book, pericope_num, _not_worked(pericope_num, book, earlier_passages))
    return f"{validator_map}\n\n{earlier}" if earlier else validator_map
