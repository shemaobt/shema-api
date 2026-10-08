"""ENG-1486 — the made-up book every canon test stands in place of Ruth is written once.

Four modules each wrote their own Fable and they had drifted: four lines parameterised in
one, a reworded sentence in the others, a different letter in the code of a third. What they
share lives in `tests/canon_harness.py` now, and these cases hold that it reads as the
passage it is asked for.
"""

from __future__ import annotations

from app.services.internalization_room.canon import book_material, parse_map
from tests.canon_harness import (
    A_FABLE_LOG_WITH_A_COMPLETE_REGISTER,
    A_FABLE_LOG_WITH_A_LAYER,
    A_FABLE_LOG_WITH_AN_INCOMPLETE_REGISTER,
    A_FABLE_LOG_WITHOUT_ONE,
    a_fable_map,
)


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


def test_a_fable_log_with_a_layer_records_one_rule_the_team_may_not_decide() -> None:
    audit = book_material._extract_audit(A_FABLE_LOG_WITH_A_LAYER)

    assert [(entry["id"], entry["do_not_decide"]) for entry in audit] == [("R1", True)]
    assert book_material._extract_checklist(A_FABLE_LOG_WITH_A_LAYER) == {}


def test_a_fable_log_without_one_records_no_rule_at_all() -> None:
    assert book_material._extract_audit(A_FABLE_LOG_WITHOUT_ONE) == []
    assert book_material._extract_checklist(A_FABLE_LOG_WITHOUT_ONE) == {}


def test_a_fable_log_with_a_complete_register_keeps_its_rule_and_says_the_register_is_done() -> (
    None
):
    audit = book_material._extract_audit(A_FABLE_LOG_WITH_A_COMPLETE_REGISTER)

    assert [(entry["id"], entry["do_not_decide"]) for entry in audit] == [("R1", True)]
    assert book_material._extract_checklist(A_FABLE_LOG_WITH_A_COMPLETE_REGISTER) == {
        "high_risk_register_complete": True
    }


def test_a_fable_log_with_an_incomplete_register_keeps_its_rule_and_says_it_is_open() -> None:
    audit = book_material._extract_audit(A_FABLE_LOG_WITH_AN_INCOMPLETE_REGISTER)

    assert [(entry["id"], entry["do_not_decide"]) for entry in audit] == [("R1", True)]
    assert book_material._extract_checklist(A_FABLE_LOG_WITH_AN_INCOMPLETE_REGISTER) == {
        "high_risk_register_complete": False
    }
