"""The serializer the design allows exactly one of.

``docs/resource_requests.md`` §4.2 forbids a second one by name, because
``rr_snapshots.document`` has to be a **copy** of the read path: what the mesa evaluates
must be what the team submitted, and a projection that drifts breaks that quietly, months
later, in the one direction nobody re-reads.

So these tests are about a round trip and about a shape, not about a feature. Everything
downstream — the read route, the freeze, the revision — is this module plus a query.
"""

from __future__ import annotations

from decimal import Decimal

from app.db.models.resource_request import RRBudgetLine, RRRequest, RRRequestSections
from app.models.resource_request import RequestDraftIn
from app.services.resource_request._document import document, split
from app.utils.resource_request_typed_fields import PROMOTED_TO_SPINE
from app.utils.resource_request_vocabularies import REQUEST_TYPES, section_field_keys


def _draft(**over: object) -> RequestDraftIn:
    payload: dict[str, object] = {
        "request_type": "traducao",
        "currency": "BRL",
        "declaration": True,
        "fields": {
            "reg_name": "Projeto Xerente",
            "amount_requested": "1200.50",
            "tpp_name": "Ana",
            "tpp_date": "2026-08-28",
            "leader_name": "Bruno",
            "leader_date": "2026-08-29",
            "lang_name": "Xerente",
        },
        "langs": [],
        "team": [{"name": "Ana", "role": "coordenação"}],
        "chrono": [],
        "budget": [
            {
                "category_key": "materiais_didaticos",
                "description": "Cartilhas",
                "quantity": "2",
                "amount": "60",
            },
            {"category_key": "bolsas_de_estudo", "description": "Bolsa", "amount": "300.25"},
        ],
        "stated_total": "360.25",
    }
    payload.update(over)
    return RequestDraftIn.model_validate(payload)


def _rows(draft: RequestDraftIn) -> tuple[RRRequest, RRRequestSections, list[RRBudgetLine]]:
    """The three tables, built from a split exactly as a service would build them."""
    parts = split(draft)
    request = RRRequest(id="r1", **parts.spine)
    sections = RRRequestSections(request_id="r1", content=parts.sections)
    budget = [RRBudgetLine(request_id="r1", **line) for line in parts.budget]
    return request, sections, budget


def test_every_type_asks_all_six_promoted_answers() -> None:
    """What licenses ``document()`` to write the six back unconditionally.

    A0's project name, item 9's amount and item 11's two signatures are structural rather
    than per-type, so there is no case where a promoted answer would have to stay *absent*.
    The module says so instead of carrying a branch that never runs — and the day a fourth
    type asks fewer, this is what fails.
    """
    for request_type in REQUEST_TYPES:
        missing = PROMOTED_TO_SPINE - section_field_keys(request_type)

        assert missing == set(), f"{request_type} does not ask {sorted(missing)}"


def test_the_document_is_the_payload_without_the_claim() -> None:
    """One shape in, one shape out: what ``GET`` hands back is what ``PATCH`` accepts.

    ``stated_total`` is the single difference, and it is not an omission — it is a claim
    about the rows, which BE-05 recomputes and refuses on mismatch. Storing it would be
    storing a derived number.
    """
    draft = _draft()

    built = document(*_rows(draft))

    assert set(built) == set(draft.model_dump(exclude={"stated_total"}))
    assert "stated_total" not in built


def test_every_answer_survives_the_round_trip() -> None:
    """The 45 go in through one dict and come back through one dict, columns and all."""
    draft = _draft()

    built = document(*_rows(draft))

    assert built["fields"] == draft.fields
    assert built["team"] == [{"name": "Ana", "role": "coordenação"}]
    assert built["declaration"] is True
    assert built["request_type"] == "traducao"


def test_a_promoted_answer_lives_in_the_column_and_not_in_the_sections() -> None:
    """*A value with two homes is a value with no owner* — the model's own rule, kept.

    The wire carries all 45 together and the storage does not: six are columns, and the
    section document must not hold a second copy that could disagree with them.
    """
    parts = split(_draft())

    assert PROMOTED_TO_SPINE & set(parts.sections["fields"]) == set()
    assert parts.spine["reg_name"] == "Projeto Xerente"
    assert parts.spine["amount_requested"] == Decimal("1200.50")
    assert parts.spine["tpp_date"].isoformat() == "2026-08-28"


def test_an_unanswered_typed_field_is_null_and_comes_back_empty() -> None:
    """Empty is *not answered*, and it has to stay distinguishable from a zero or a date."""
    draft = _draft(
        fields={
            "reg_name": "",
            "amount_requested": "",
            "tpp_name": "",
            "tpp_date": "",
            "leader_name": "",
            "leader_date": "",
        }
    )
    parts = split(draft)

    assert parts.spine["amount_requested"] is None
    assert parts.spine["tpp_date"] is None

    built = document(*_rows(draft))

    assert built["fields"]["amount_requested"] == ""
    assert built["fields"]["tpp_date"] == ""


def test_money_comes_back_as_the_column_holds_it() -> None:
    """``"1200.5"`` returns ``"1200.50"``, and that is a normalisation rather than a loss.

    The column is ``Numeric(14, 2)`` and the DTO already refused a third decimal on the way
    in, so no digit the client sent is dropped — only the shape of the zero it did not send.
    """
    draft = _draft(fields={**_draft().fields, "amount_requested": "1200.5"})

    built = document(*_rows(draft))

    assert built["fields"]["amount_requested"] == "1200.50"


def test_money_is_a_string_on_the_wire_and_never_a_float() -> None:
    """A float between the team and the mesa is ``0.1 + 0.2`` on a screen that moves money."""
    built = document(*_rows(_draft()))

    for line in built["budget"]:
        assert line["amount"] is None or isinstance(line["amount"], str)
    assert isinstance(built["fields"]["amount_requested"], str)


def test_budget_lines_come_back_in_a_stable_order() -> None:
    """Two reads of one request produce the same bytes, so a freeze can be compared to one.

    Without it a snapshot and a later read could differ by row order alone, which would make
    the freeze look broken when nothing had moved.
    """
    draft = _draft()
    request, sections, budget = _rows(draft)

    forwards = document(request, sections, budget)
    backwards = document(request, sections, list(reversed(budget)))

    assert forwards == backwards
    assert [line["category_key"] for line in forwards["budget"]] == [
        "bolsas_de_estudo",
        "materiais_didaticos",
    ]


def test_a_request_whose_sections_row_is_missing_reads_as_empty() -> None:
    """One case produces it — a dump taken mid-write — and a 500 there reads worse."""
    draft = _draft()
    request, _sections, budget = _rows(draft)

    built = document(request, None, budget)

    assert built["team"] == []
    assert built["fields"]["reg_name"] == "Projeto Xerente"
