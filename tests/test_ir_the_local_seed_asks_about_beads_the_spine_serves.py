"""The questions the local seed raises are about beads the spine serves.

The inbox names a card by looking its ``(pericope, element_key)`` up in the catalogue, and
a key the spine does not yield serves the card with no name and no error, so a seed written
before the keys changed shape draws a local stack of cards about nothing.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.services.internalization_room.canon.elements import element_keys

SEED = Path(__file__).resolve().parent.parent / "scripts" / "seed_local_content.sql"

INSERT = re.compile(
    r"insert into ir_questions\s*\((?P<columns>[^)]*)\)\s*select\s+(?P<values>.*?)\s+from projects",
    re.DOTALL | re.IGNORECASE,
)


def _top_level_commas(values: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    quoted = False
    start = 0
    for index, char in enumerate(values):
        if char == "'":
            quoted = not quoted
        elif not quoted and char == "(":
            depth += 1
        elif not quoted and char == ")":
            depth -= 1
        elif not quoted and depth == 0 and char == ",":
            parts.append(values[start:index].strip())
            start = index + 1
    parts.append(values[start:].strip())
    return parts


def _questions() -> list[dict[str, str]]:
    questions = []
    for found in INSERT.finditer(SEED.read_text()):
        columns = [column.strip() for column in found["columns"].split(",")]
        values = _top_level_commas(found["values"])
        questions.append(dict(zip(columns, values, strict=True)))
    return questions


def test_every_question_the_seed_raises_points_at_a_bead_its_passage_serves() -> None:
    questions = _questions()
    inserts = SEED.read_text().lower().count("insert into ir_questions")
    assert len(questions) == inserts > 0, "an insert of the seed was not read as a question"

    for question in questions:
        pericope = question["pericope"].strip("'")
        assert question["element_key"].strip("'") in element_keys(pericope), (
            f"{question['id']} asks about {question['element_key']}, "
            f"which {pericope}'s spine does not yield"
        )
