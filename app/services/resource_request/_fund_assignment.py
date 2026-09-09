"""GATE-01 D4's invariant, in the one place both approval doors read it.

**A request does not enter ``aprovado`` with ``fund_id IS NULL``.** Approving commits
money and BE-07 cannot debit a fund it was never told, so the fund the mesa assigns at
triage (BE-11, OBT-470) has to be there before the column changes. ``NULL`` is not a gap:
it is the legitimate state of a request still in ``triagem``, which is exactly why this is
a **service rule and deliberately not a DDL CHECK** — the same null is correct one column
earlier, and a constraint cannot tell the two moments apart.

**Since GATE-02 D6 approval has two doors** — recording the decision in Parte C
(``save_evaluation``) and dragging the card on the board (``move_request``) — and the rule
restricts both. It has one owner rather than two implementations because a rule written
twice is a rule that will be relaxed once: BE-08 (OBT-457) fired it inline in
``guard_stage_entry`` while BE-11 was still unwritten, and this module is where it moved.
Both doors reach it through ``guard_stage_entry``, which is the single point where a stage
change becomes an entry into ``aprovado``, so neither router repeats the check and no
third writer can appear without passing through it.

The refusal is a ``ConflictError`` — a 409 — and not a validation error, because nothing
the caller sent is malformed: the request is in a state that does not admit the move, and
the way out is to assign a fund, which the message says.
"""

from app.core.exceptions import ConflictError
from app.db.models.resource_request import RRRequest


def require_assigned_fund(request: RRRequest) -> str:
    """The fund this request will commit against, or the refusal that it has none."""
    if request.fund_id is None:
        raise ConflictError(
            "A request does not enter aprovado with no fund: "
            "the mesa assigns one at triage before approving."
        )
    return request.fund_id
