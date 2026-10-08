"""ENG-1486 — the made-up book every canon test stands in place of Ruth is written once.

Four modules each wrote their own Fable and they had drifted: four lines parameterised in
one, a reworded sentence in the others, a different letter in the code of a third. What they
share lives in `tests/canon_harness.py` now, and these cases hold that it reads as the
passage it is asked for.
"""

from __future__ import annotations

from app.services.internalization_room.canon import parse_map
from tests.canon_harness import a_fable_map


def test_the_fable_builder_makes_the_numbered_passage_it_is_asked_for() -> None:
    meaning_map = parse_map.parse_map(a_fable_map(3))

    assert meaning_map.pericope_num == "Q03"
    assert meaning_map.reference == "Fable 1:3-4"
    assert meaning_map.book == "Fable"
    assert [scene.verses for scene in meaning_map.scenes] == ["v.3-4"]


def test_the_fable_builder_is_the_first_passage_and_finished_unless_told_otherwise() -> None:
    meaning_map = parse_map.parse_map(a_fable_map())

    assert meaning_map.pericope_num == "Q01"
    assert meaning_map.sta_status == "complete"


def test_the_fable_builder_carries_the_survey_status_it_is_given() -> None:
    meaning_map = parse_map.parse_map(a_fable_map(sta_status="pending"))

    assert meaning_map.sta_status == "pending"
