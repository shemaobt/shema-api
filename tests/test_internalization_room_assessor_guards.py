"""The assessor's fail-closed parser: every evidence row must quote the team exactly and
survive negation, polarity, and duplicate guards."""

import json

from app.services.internalization_room.comprehension.assessor import (
    excerpt_drops_nearby_negation,
    is_bare_polar_answer,
    is_exact_excerpt,
    is_semantically_empty_answer,
    parse_turn_assessor_decision,
    semantic_excerpt_has_unresolved_polarity,
)

ALLOWED = ["proposition:P03:P1"]


def _raw(rows: list[dict], **extra) -> str:
    return json.dumps({"observations": rows, **extra})


def _row(**overrides) -> dict:
    row = {
        "checkpoint_id": ALLOWED[0],
        "result": "demonstrated",
        "evidence_excerpt": "Noemi voltou",
        "rationale": "names the return",
    }
    row.update(overrides)
    return row


def test_a_grounded_row_with_an_exact_quote_survives() -> None:
    parsed = parse_turn_assessor_decision(_raw([_row()]), "Noemi voltou para Belém", ALLOWED)
    assert parsed is not None
    observations, _ = parsed
    assert len(observations) == 1
    assert observations[0].result == "demonstrated"


def test_a_row_quoting_words_the_team_never_said_is_dropped() -> None:
    parsed = parse_turn_assessor_decision(
        _raw([_row(evidence_excerpt="Rute ficou no campo")]), "Noemi voltou", ALLOWED
    )
    assert parsed is not None and parsed[0] == []


def test_a_quote_that_drops_a_nearby_negation_is_dropped() -> None:
    parsed = parse_turn_assessor_decision(
        _raw([_row(evidence_excerpt="Noemi voltou")]), "não foi que Noemi voltou", ALLOWED
    )
    assert parsed is not None and parsed[0] == []


def test_a_proposition_inside_uncertainty_is_not_positive_evidence() -> None:
    parsed = parse_turn_assessor_decision(
        _raw([_row(evidence_excerpt="Noemi voltou")]),
        "não tenho certeza se Noemi voltou",
        ALLOWED,
    )
    assert parsed is not None and parsed[0] == []


def test_a_question_then_denial_is_not_an_assertion() -> None:
    parsed = parse_turn_assessor_decision(
        _raw([_row(evidence_excerpt="Noemi voltou")]), "Noemi voltou? Não.", ALLOWED
    )
    assert parsed is not None and parsed[0] == []


def test_an_unknown_checkpoint_id_is_dropped() -> None:
    parsed = parse_turn_assessor_decision(
        _raw([_row(checkpoint_id="proposition:P03:P99")]), "Noemi voltou", ALLOWED
    )
    assert parsed is not None and parsed[0] == []


def test_the_model_cannot_return_carry_or_stt_results() -> None:
    for result in ("carry_to_refine", "stt_uncertain", "no_evidence"):
        parsed = parse_turn_assessor_decision(_raw([_row(result=result)]), "Noemi voltou", ALLOWED)
        assert parsed is not None and parsed[0] == []


def test_two_competing_rows_for_one_checkpoint_cancel_each_other() -> None:
    parsed = parse_turn_assessor_decision(
        _raw([_row(), _row(result="conflict", evidence_excerpt="Noemi voltou")]),
        "Noemi voltou",
        ALLOWED,
    )
    assert parsed is not None and parsed[0] == []


def test_extra_keys_on_a_row_fail_that_row_closed() -> None:
    parsed = parse_turn_assessor_decision(_raw([_row(extra_field="x")]), "Noemi voltou", ALLOWED)
    assert parsed is not None and parsed[0] == []


def test_unparseable_output_fails_the_whole_envelope() -> None:
    assert parse_turn_assessor_decision("nada de json", "Noemi voltou", ALLOWED) is None


def test_practice_needs_an_exact_quote_and_an_explicit_report() -> None:
    utterance = "já ensaiamos esta cena na nossa língua"
    parsed = parse_turn_assessor_decision(
        _raw(
            [],
            mother_tongue_practice_reported=True,
            practice_evidence_excerpt=utterance,
        ),
        utterance,
        ALLOWED,
    )
    assert parsed is not None and parsed[1] is True

    parsed = parse_turn_assessor_decision(
        _raw(
            [],
            mother_tongue_practice_reported=True,
            practice_evidence_excerpt="falamos terena",
        ),
        "falamos terena",
        ALLOWED,
    )
    assert parsed is not None and parsed[1] is False


def test_bare_polar_answers_are_semantically_empty() -> None:
    for text in ("sim", "não", "isso mesmo", "aham", "ok"):
        assert is_bare_polar_answer(text)
        assert is_semantically_empty_answer(text)
    assert not is_bare_polar_answer("Noemi voltou")
    assert is_semantically_empty_answer("não sei")
    assert not is_semantically_empty_answer("sim, Noemi voltou para Belém")


def test_excerpt_matching_ignores_case_and_spacing_but_not_content() -> None:
    assert is_exact_excerpt("NOEMI  voltou", "noemi voltou para belém")
    assert not is_exact_excerpt("noemi partiu", "noemi voltou")


def test_polarity_guard_accepts_a_plainly_asserted_quote() -> None:
    assert not semantic_excerpt_has_unresolved_polarity(
        "Noemi voltou", "Noemi voltou para Belém", positive_result=True
    )


def test_negation_dropping_guard_sees_nearby_negators() -> None:
    assert excerpt_drops_nearby_negation("voltou", "ela não voltou")
    assert not excerpt_drops_nearby_negation("não voltou", "ela não voltou")


def test_negation_dropping_guard_ignores_ordinary_portuguese_function_words() -> None:
    assert not excerpt_drops_nearby_negation("campo de Boaz", "Rute foi trabalhar no campo de Boaz")
    assert not excerpt_drops_nearby_negation(
        "tempo da colheita", "Noemi voltou para Belém no tempo da colheita"
    )
    assert not excerpt_drops_nearby_negation("para Belém", "Noemi voltou, né, para Belém")
