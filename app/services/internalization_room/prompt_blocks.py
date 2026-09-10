from __future__ import annotations

from app.services.internalization_room.canon.book_material import (
    preservation_rules,
    story_so_far,
)
from app.services.internalization_room.canon.parse_map import load_map
from app.services.internalization_room.coverage import remaining


def coverage_status_block(coverage_state: dict[str, str], pericope_num: str) -> str:
    left = remaining(coverage_state, pericope_num)
    if not left:
        return "REMAINING: (nada — todos os elementos foram trabalhados pela equipe)"
    lines = ["REMAINING (ainda não trabalhados pela equipe, nas palavras deles):"]
    lines.extend(f"- [{element.key}] {element.label}" for element in left)
    return "\n".join(lines)


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
