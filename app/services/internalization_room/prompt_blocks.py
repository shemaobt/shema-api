from __future__ import annotations

from app.services.internalization_room.canon.book_material import story_so_far
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
