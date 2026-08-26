"""What the server refuses, per request type (BE-05, OBT-454).

The shape is always the same: build a payload that is right, assert it validates, then
change one thing and assert the refusal names the thing. A fixture that passes both the
right and the wrong implementation distinguishes nothing, so every case here moves a
value that only the rule under test looks at.

Nothing mounts a route. BE-04 owns the endpoints; what is under test is the model a
route will hand its body to, which is where `docs/resource_requests.md` §8.5 put the
field-level error.
"""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.models.resource_request import (
    BudgetLineIn,
    EvaluationIn,
    RequestDraftIn,
    RequestSubmissionIn,
)
from app.utils import resource_request_vocabularies as v
from app.utils.resource_request_totals import sum_budget, sum_score

TYPES = list(v.REQUEST_TYPES)

#: One amount on the first category and nothing anywhere else, so the total is a number
#: a reader can check by eye against the assertions below.
FIRST_AMOUNT = Decimal("1500.00")


def budget(amounts: dict[str, Decimal] | None = None) -> list[dict[str, object]]:
    """All 26 rows, only the named ones carrying money."""
    amounts = amounts or {v.BUDGET_CATEGORY_KEYS[0]: FIRST_AMOUNT}
    return [
        {"category_key": key, "description": "", "quantity": None, "amount": amounts.get(key)}
        for key in v.BUDGET_CATEGORY_KEYS
    ]


def answers(request_type: str) -> dict[str, str]:
    """Every required field answered, and nothing that the type does not ask."""
    filled = dict.fromkeys(v.REQUIRED_TEXT_FIELDS[request_type], "preenchido")
    filled["tpp_date"] = "2026-08-25"
    filled["leader_date"] = "2026-08-25"
    for key in filled:
        allowed = v.VOCABULARY_VALUES.get(key)
        if allowed:
            filled[key] = allowed[0]
    return filled


def payload(request_type: str, **overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "request_type": request_type,
        "currency": "BRL",
        "fields": answers(request_type),
        "declaration": True,
        "langs": [],
        "chrono": [{"act": "Oficina", "start": "2026-09", "end": "2026-10", "notes": ""}],
        "budget": budget(),
        "stated_total": FIRST_AMOUNT,
    }
    if request_type in v.TYPES_WITH_TEAM:
        body["team"] = [{"name": "Ana", "role": "Tradutora", "qual": "", "ded": "integral"}]
    if request_type in v.TYPES_WITH_TRAINING_PROFILE:
        body["checks"] = {"teamtype": ["tradutores"], "trainformat": ["cursos"]}
    return body | overrides


def refusal(model: type, body: dict[str, object]) -> str:
    with pytest.raises(ValidationError) as caught:
        model(**body)
    return str(caught.value)


# ── The three types, submitted whole ─────────────────────────────────────────


@pytest.mark.parametrize("request_type", TYPES)
def test_a_complete_submission_of_each_type_validates(request_type):
    submitted = RequestSubmissionIn(**payload(request_type))

    assert submitted.request_type.value == request_type
    assert len(submitted.budget) == 26
    assert sum_budget(line.amount for line in submitted.budget) == FIRST_AMOUNT


@pytest.mark.parametrize("request_type", TYPES)
def test_a_draft_of_each_type_may_be_almost_empty(request_type):
    """A draft is filled over days; refusing it for being unfinished refuses the form."""
    draft = RequestDraftIn(request_type=request_type, fields={}, budget=[])

    assert draft.declaration is False
    assert draft.budget == []


# ── Per-type section requirements ────────────────────────────────────────────


def test_equipamentos_has_no_team_table_and_may_not_send_one():
    body = payload("equipamentos", team=[{"name": "Ana", "role": "", "qual": "", "ded": ""}])

    assert "has no team table" in refusal(RequestSubmissionIn, body)


@pytest.mark.parametrize("request_type", ["traducao", "treinamento"])
def test_the_types_that_render_a_team_need_a_row_to_submit(request_type):
    assert "at least one team row" in refusal(RequestSubmissionIn, payload(request_type, team=[]))


def test_treinamento_needs_a5_and_the_others_may_not_send_it():
    assert "has no A5 section" in refusal(
        RequestSubmissionIn, payload("traducao", checks={"teamtype": ["tradutores"]})
    )
    assert "section A5 needs" in refusal(
        RequestSubmissionIn, payload("treinamento", checks={"teamtype": [], "trainformat": []})
    )


def test_traducao_has_no_langs_table_and_may_not_send_one():
    """A1 renders *full* for ``traducao``: twelve text fields and no table of names."""
    body = payload("traducao", langs=[{"name": "Ticuna", "code": "tca"}])

    assert "has no langs table" in refusal(RequestSubmissionIn, body)


@pytest.mark.parametrize(
    ("table", "request_type"),
    [("langs", "equipamentos"), ("team", "traducao"), ("chrono", "traducao")],
)
def test_a_row_may_not_carry_a_column_the_table_never_had(table, request_type):
    """The ``fields`` rule one level down — a row is answers to columns.

    Without it a row carried any key at all and was stored as though the question had
    been put, which is the *absent means not asked* distinction the mesa reads losing
    its meaning inside the tables (review of PR #253).
    """
    row = dict.fromkeys(v.TABLE_ROW_KEYS[table], "") | {"observacao": "inventada"}

    assert f"{table} has no column: observacao" in refusal(
        RequestDraftIn, payload(request_type, **{table: [row]})
    )


@pytest.mark.parametrize("table", ["langs", "team", "chrono"])
def test_the_columns_a_table_does_have_are_accepted(table):
    request_type = "treinamento"
    row = dict.fromkeys(v.TABLE_ROW_KEYS[table], "x")

    assert RequestDraftIn(**payload(request_type, **{table: [row]}))


def test_a_key_the_type_never_renders_is_refused_even_in_a_draft():
    """Absent means *not asked*, and storing an answer to an unasked question erases that."""
    body = {"request_type": "equipamentos", "fields": {"people_name": "Ticuna"}}

    assert "does not ask: people_name" in refusal(RequestDraftIn, body)


def test_the_same_key_is_accepted_for_the_type_that_does_render_it():
    """The other half — without it the rule above would pass by refusing everything."""
    draft = RequestDraftIn(request_type="traducao", fields={"people_name": "Ticuna"})

    assert draft.fields["people_name"] == "Ticuna"


@pytest.mark.parametrize("request_type", TYPES)
def test_the_signatures_and_the_declaration_are_submission_time_only(request_type):
    unsigned = dict(answers(request_type))
    for key in ("tpp_name", "tpp_date", "leader_name", "leader_date"):
        unsigned[key] = ""

    RequestDraftIn(**payload(request_type, fields=unsigned, declaration=False))

    assert "unanswered at submission" in refusal(
        RequestSubmissionIn, payload(request_type, fields=unsigned)
    )
    assert "declaration must be accepted" in refusal(
        RequestSubmissionIn, payload(request_type, declaration=False)
    )


# ── Vocabularies ─────────────────────────────────────────────────────────────


def test_an_answer_outside_its_vocabulary_is_refused_and_the_valid_one_is_not():
    valid = v.VOCABULARY_VALUES["lang_script"][0]

    assert RequestDraftIn(request_type="traducao", fields={"lang_script": valid})
    assert "lang_script: answer outside its vocabulary" in refusal(
        RequestDraftIn, {"request_type": "traducao", "fields": {"lang_script": "Cuneiforme"}}
    )


def test_the_vocabulary_holds_at_submission_too_and_not_only_in_the_draft():
    """The draft's rules are not a lighter set that submission replaces.

    Pydantic runs a base class's validators before a subclass's, so every shape rule
    above still runs here — this is the assertion that says so, because a subclass that
    happened to shadow one would look identical from the outside.
    """
    wrong = dict(answers("traducao"))
    wrong["lang_script"] = "Cuneiforme"

    assert "lang_script: answer outside its vocabulary" in refusal(
        RequestSubmissionIn, payload("traducao", fields=wrong)
    )


def test_an_unanswered_select_stays_empty_rather_than_failing_its_vocabulary():
    """Empty is *not answered*, which every vocabulary field is allowed to be."""
    assert RequestDraftIn(request_type="traducao", fields={"lang_script": ""})


def test_the_two_checkbox_sets_are_checked_against_their_own_lists():
    body = payload("treinamento", checks={"teamtype": ["arquitetos"], "trainformat": ["cursos"]})

    assert "unknown option: arquitetos" in refusal(RequestSubmissionIn, body)


# ── The 26 categories ────────────────────────────────────────────────────────


def test_an_invented_category_is_refused():
    assert "unknown budget category: cafezinho" in refusal(
        BudgetLineIn, {"category_key": "cafezinho"}
    )


def test_a_submission_needs_all_twenty_six_and_a_draft_does_not():
    short = budget()[:25]
    missing = v.BUDGET_CATEGORY_KEYS[25]

    RequestDraftIn(**payload("traducao", budget=short, stated_total=None))

    assert f"missing category at submission: {missing}" in refusal(
        RequestSubmissionIn, payload("traducao", budget=short)
    )


def test_the_same_category_twice_is_refused_at_draft_time():
    doubled = [*budget(), {"category_key": v.BUDGET_CATEGORY_KEYS[0], "amount": Decimal("1.00")}]

    assert "budget category sent twice" in refusal(
        RequestDraftIn, payload("traducao", budget=doubled, stated_total=None)
    )


# ── Money ────────────────────────────────────────────────────────────────────


def test_a_sub_cent_amount_is_refused_rather_than_rounded():
    assert "more than two decimal places" in refusal(
        BudgetLineIn, {"category_key": v.BUDGET_CATEGORY_KEYS[0], "amount": Decimal("0.0001")}
    )


@pytest.mark.parametrize("amount", ["1E+30", "1000000000000"])
def test_an_amount_too_large_for_the_column_is_refused_and_not_raised(amount):
    """``Numeric(14, 2)`` holds twelve integer digits, and the guard runs before the
    quantize.

    ``quantize`` signals ``InvalidOperation`` — not ``ValueError`` — once the result
    needs more digits than the decimal context carries, and Pydantic converts only
    ``ValueError``, so before this the payload left as a 500 instead of the 422 every
    other refusal here returns (review of PR #253).
    """
    body = {"category_key": v.BUDGET_CATEGORY_KEYS[0], "amount": Decimal(amount)}

    assert "outside the range money is stored in" in refusal(BudgetLineIn, body)


def test_the_largest_amount_the_column_holds_is_accepted():
    body = {"category_key": v.BUDGET_CATEGORY_KEYS[0], "amount": Decimal("999999999999.99")}

    assert BudgetLineIn(**body).amount == Decimal("999999999999.99")


def test_an_oversized_stated_total_is_refused_on_its_own_field():
    """The second door the same arithmetic reaches, and it locates on the claim."""
    with pytest.raises(ValidationError) as caught:
        RequestDraftIn(**payload("traducao", stated_total=Decimal("1E+30")))

    assert [error["loc"] for error in caught.value.errors()] == [("stated_total",)]


def test_a_negative_line_passes_a_draft_and_fails_a_submission():
    """The one rule that differs between the two doors, and it differs deliberately."""
    key = v.BUDGET_CATEGORY_KEYS[3]
    rows = budget({v.BUDGET_CATEGORY_KEYS[0]: FIRST_AMOUNT, key: Decimal("-500.00")})
    total = FIRST_AMOUNT - Decimal("500.00")

    RequestDraftIn(**payload("traducao", budget=rows, stated_total=total))

    assert f"negative amount: {key}" in refusal(
        RequestSubmissionIn, payload("traducao", budget=rows, stated_total=total)
    )


# ── The total is a claim ─────────────────────────────────────────────────────


def test_a_total_that_matches_its_rows_is_accepted():
    rows = budget(
        {v.BUDGET_CATEGORY_KEYS[0]: Decimal("10.50"), v.BUDGET_CATEGORY_KEYS[1]: Decimal("4.50")}
    )

    assert RequestDraftIn(**payload("traducao", budget=rows, stated_total=Decimal("15.00")))


def test_a_total_one_cent_off_is_refused_and_the_message_carries_the_real_sum():
    """One cent, because the tolerance is zero and a bigger drift would not prove that.

    Sub-cent input is already refused, so both sides are exact and there is no rounding
    left to tolerate — a margin here would only license a lie the size of the margin.
    """
    rows = budget({v.BUDGET_CATEGORY_KEYS[0]: Decimal("10.50")})

    assert "they sum to 10.50" in refusal(
        RequestDraftIn, payload("traducao", budget=rows, stated_total=Decimal("10.51"))
    )


def test_no_total_sent_is_no_claim_to_check():
    assert RequestDraftIn(**payload("traducao", stated_total=None))


def test_the_refusal_is_located_on_the_field_that_carries_the_claim():
    """§8.5's measurement, pinned: the client can point at the box that is wrong."""
    with pytest.raises(ValidationError) as caught:
        RequestDraftIn(**payload("traducao", stated_total=Decimal("99.00")))

    assert [error["loc"] for error in caught.value.errors()] == [("stated_total",)]


# ── The evaluation ───────────────────────────────────────────────────────────


def scores(request_type: str, values: list[int | None]) -> list[dict[str, object]]:
    return [
        {"criterion_key": key, "score": score}
        for key, score in zip(v.CRITERION_KEYS[request_type], values, strict=True)
    ]


@pytest.mark.parametrize("request_type", TYPES)
def test_an_evaluation_of_each_type_takes_its_own_six_criteria(request_type):
    evaluation = EvaluationIn(
        request_type=request_type,
        scores=scores(request_type, [5, 4, 3, 2, 1, 0]),
        decision="approved",
        stated_total=15,
    )

    assert sum_score(score.score for score in evaluation.scores) == 15
    assert evaluation.decision.value == "approved"


def test_a_criterion_from_another_type_is_refused():
    body = {
        "request_type": "treinamento",
        "scores": scores("treinamento", [0] * 6),
    }
    body["scores"][0]["criterion_key"] = v.CRITERION_KEYS["traducao"][0]

    assert "criterion does not belong to treinamento" in refusal(EvaluationIn, body)


def test_a_missing_criterion_is_refused():
    body = {"request_type": "traducao", "scores": scores("traducao", [0] * 6)[:5]}

    assert "missing criterion" in refusal(EvaluationIn, body)


@pytest.mark.parametrize("bad", [6, -1, 3.7])
def test_a_score_outside_zero_to_five_is_refused(bad):
    """3.7 is here because the frontend's own input accepts it — the export sets no step."""
    body = {"request_type": "traducao", "scores": scores("traducao", [0] * 6)}
    body["scores"][0]["score"] = bad

    assert refusal(EvaluationIn, body)


def test_not_scored_is_not_a_scored_zero():
    """`None` contributes nothing and a total that counted it as zero would report a
    judgement nobody made — which is why BE-02 keeps the column nullable."""
    evaluation = EvaluationIn(
        request_type="traducao",
        scores=scores("traducao", [5, 5, None, None, None, None]),
        stated_total=10,
    )

    assert [score.score for score in evaluation.scores].count(None) == 4


def test_an_evaluation_total_that_disagrees_with_its_scores_is_refused():
    body = {
        "request_type": "traducao",
        "scores": scores("traducao", [5, 5, 5, 5, 5, 5]),
        "stated_total": 29,
    }

    assert "they sum to 30" in refusal(EvaluationIn, body)


def test_a_decision_outside_the_four_strings_is_refused():
    body = {"request_type": "traducao", "scores": scores("traducao", [0] * 6), "decision": "maybe"}

    assert refusal(EvaluationIn, body)


def test_the_evaluation_carries_no_evaluator_and_no_date():
    """BE-06 stamps both from the session; a payload that could carry them could lie."""
    body = {
        "request_type": "traducao",
        "scores": scores("traducao", [0] * 6),
        "evaluator_id": "someone",
    }

    assert refusal(EvaluationIn, body)
