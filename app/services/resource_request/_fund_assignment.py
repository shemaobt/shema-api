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

**Nor does it enter ``aprovado`` against a fund that is no longer on offer** (OBT-645,
27/oct/2026). Retirement (BE-10, OBT-471) refuses only while a request on the fund is
undecided, so a card decided ``condicional``, ``revisar`` or ``recusado`` keeps pointing at
a fund that retires afterwards — and the board, whose graph is total, could then drag it
into ``aprovado`` and append a fresh deduction against a fund that ended. The fund is asked
of the list of choice here, at the door both approvals already pass, and refused with the
assignment's own answer (``require_choosable``: 422, the same sentence), because that is
the fact and its way out — the mesa assigns a fund on offer, exactly as it would for a
request with none. **Leaving ``aprovado`` is not refused**: its reversal compensates what
was already written against the fund, which is the history a retirement keeps.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.db.models.resource_request import RRRequest
from app.services.resource_request._fund_choices import choosable_funds, require_choosable


async def require_assigned_fund(db: AsyncSession, request: RRRequest) -> str:
    """The fund this request will commit against — refused if it has none, or if that
    fund is no longer on offer."""
    if request.fund_id is None:
        raise ConflictError(
            "A request does not enter aprovado with no fund: "
            "the mesa assigns one at triage before approving."
        )
    require_choosable(await choosable_funds(db), request.fund_id)
    return request.fund_id
