"""The one place a request becomes a document, and the one place a payload becomes rows.

The design forbids a second serializer by name (``docs/resource_requests.md`` §4.2): the
sections are stored as *one document* rather than as a row per answer precisely so that
``rr_snapshots.document`` is a **copy** of the read path and not a projection of it — *"so
submission is a copy and not a projection, and BE-04 never grows a second serializer that
can drift from the read path."*

So there is one builder, ``document()``, and everything that needs the content of a request
calls it: the read route, the freeze at submission, and the revision that reopens a frozen
one. A drift between what the mesa evaluated and what the team sees cannot be introduced by
editing one of three functions, because there is one.

**The document is the payload shape, minus the claim.** It is ``RequestDraftIn`` without
``stated_total`` — so what ``GET`` hands back is what ``PATCH`` accepts, and what the
snapshot freezes is the same bytes again. *The mesa evaluated what the team submitted* is
then true by construction rather than by a test comparing two shapes. ``stated_total`` is
absent because it is a **claim** about the rows, recomputed by BE-05 and refused on
mismatch; storing it would be storing a derived number.

The envelope around the document — id, stage, timestamps, the revision link — is mutable
state, is not part of the frozen thing, and is built by the DTOs rather than here.

**Absent is not empty**, and the contract's *empty means not answered, absent means not
asked* is a difference the mesa reads. It costs nothing here for one measured reason: all
three request types ask all six promoted answers — A0's name, item 9's amount and item 11's
two signatures are structural, not per-type — so the six are always written back.
``test_document.py`` pins that fact rather than this module carrying a branch that never
runs; the day a fourth type asks fewer, the test fails and whoever adds it decides.

The six promoted answers travel between ``fields`` and the spine through
``app/utils/resource_request_typed_fields.py`` — see that module for why the split exists
and why two of the six change type on the way.
"""

from decimal import Decimal
from typing import Any, NamedTuple

from app.db.models.resource_request import RRBudgetLine, RRRequest, RRRequestSections
from app.models.resource_request import RequestDraftIn
from app.utils.resource_request_typed_fields import (
    PROMOTED_TO_SPINE,
    SPINE_DAY_FIELDS,
    SPINE_MONEY_FIELDS,
    SPINE_TEXT_FIELDS,
    parse_day,
    parse_money,
    render_day,
    render_money,
)


class Split(NamedTuple):
    """A validated payload, taken apart into the three tables that store it."""

    spine: dict[str, Any]
    sections: dict[str, Any]
    budget: list[dict[str, Any]]


def split(draft: RequestDraftIn) -> Split:
    """Take a validated payload apart into what each of the three tables holds.

    Parsing here is total: the DTO already refused an amount or a date that cannot be read,
    through the same two functions this calls.

    A promoted key the type does not ask is simply not in ``fields``, and the column keeps
    its empty default — which is the storage side of *absent is not empty*, since a column
    cannot be absent.
    """
    answers = dict(draft.fields)

    spine: dict[str, Any] = {
        "request_type": draft.request_type,
        "currency": draft.currency,
        "declaration": draft.declaration,
    }
    for key in SPINE_TEXT_FIELDS:
        spine[key] = answers.pop(key, "")
    for key in SPINE_MONEY_FIELDS:
        spine[key] = parse_money(answers.pop(key, ""))
    for key in SPINE_DAY_FIELDS:
        spine[key] = parse_day(answers.pop(key, ""))

    sections: dict[str, Any] = {
        "fields": answers,
        "langs": [dict(row) for row in draft.langs],
        "team": [dict(row) for row in draft.team],
        "chrono": [dict(row) for row in draft.chrono],
        "checks": draft.checks.model_dump(),
    }

    budget = [
        {
            "category_key": line.category_key,
            "description": line.description,
            "quantity": line.quantity,
            "amount": line.amount,
        }
        for line in draft.budget
    ]

    return Split(spine=spine, sections=sections, budget=budget)


def document(
    request: RRRequest,
    sections: RRRequestSections | None,
    budget: list[RRBudgetLine],
) -> dict[str, Any]:
    """The request as a document: what ``GET`` returns and what submission freezes.

    ``sections`` may be missing rather than required, because a request row can outlive its
    sections row in exactly one case — a database restored from a dump taken mid-write — and
    answering with an empty document reads better there than a 500.

    Budget lines come back **sorted by category key** rather than in insertion order, so two
    reads of the same request produce the same bytes. Without it a snapshot and a later read
    could differ by row order alone, which would make the freeze look broken when nothing
    had moved.
    """
    content: dict[str, Any] = dict(sections.content) if sections is not None else {}

    answers: dict[str, str] = dict(content.get("fields", {}))
    for key in SPINE_TEXT_FIELDS:
        answers[key] = getattr(request, key) or ""
    for key in SPINE_MONEY_FIELDS:
        answers[key] = render_money(getattr(request, key))
    for key in SPINE_DAY_FIELDS:
        answers[key] = render_day(getattr(request, key))

    return {
        "request_type": request.request_type.value,
        "currency": request.currency.value,
        "declaration": request.declaration,
        "fields": answers,
        "langs": content.get("langs", []),
        "team": content.get("team", []),
        "chrono": content.get("chrono", []),
        "checks": content.get("checks", {}),
        "budget": [
            {
                "category_key": line.category_key,
                "description": line.description,
                "quantity": _plain(line.quantity),
                "amount": _plain(line.amount),
            }
            for line in sorted(budget, key=lambda line: line.category_key)
        ],
    }


def _plain(value: Decimal | None) -> str | None:
    """Money as the string it was sent as, never a float.

    A ``Decimal`` does not survive JSON, and rendering it as a float would put
    ``0.1 + 0.2`` between the team and the mesa. It is the choice the wire already makes:
    ``BudgetLineIn`` accepts a string and Pydantic builds the ``Decimal`` from it.
    """
    return None if value is None else str(value)


__all__ = ["PROMOTED_TO_SPINE", "Split", "document", "split"]
