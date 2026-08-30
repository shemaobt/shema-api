from datetime import datetime
from decimal import Decimal
from typing import NamedTuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UnknownReferenceError
from app.db.models.auth import User
from app.db.models.resource_request import (
    RRMovementKind,
    RRRequestFieldHistory,
    RRStage,
)
from app.services.resource_request._fund_choices import choosable_funds
from app.services.resource_request._transition import unreversed_deduction
from app.services.resource_request.append_movement import append_movement
from app.services.resource_request.get_request import get_request
from app.services.resource_request.reverse_movement import reverse_movement


class FundMoved(NamedTuple):
    """One fund's *comprometido* after a swap — FE-15's ``FundDelta``, twice over.

    Negative on the fund the request left, positive on the one it joined. A swap is the
    only operation in the module that moves two funds, which is why this is a list on the
    answer and a single value on a board move.
    """

    fund_id: str
    committed_delta: Decimal


class FundAssignment(NamedTuple):
    """What the assignment did, as values read before the commit expires the rows.

    ``changed`` is ``False`` when the request already pointed at that fund: nothing is
    written — no history row and no movement — which is the same answer a board move gives
    for a card already in its column. Asking for the state something is in is not an
    illegal request.
    """

    request_id: str
    fund_id: str
    previous_fund_id: str | None
    changed: bool
    assigned_by: str
    assigned_at: datetime | None
    fund_deltas: tuple[FundMoved, ...]
    movement_ids: tuple[str, ...]


async def assign_fund(
    db: AsyncSession, request_id: str, fund_id: str, user: User, app_key: str
) -> FundAssignment:
    """The mesa's triage decision: which fund this request draws from (GATE-01 D4).

    **Nothing in the form says it**, which is the whole reason this endpoint exists: the 45
    questions stay 45 and ``rr_requests.fund_id`` arrives null, so someone has to write it
    and the client answered *"somente a mesa"* (28/aug/2026, re-asked). The capability is
    ``assign_fund``, held by the mesa alone — a Gestor session is refused here even though
    it moves the board and allocates money, and that refusal is the client's sentence and
    not a default of ours.

    **A retired fund is not assignable.** The choices come from ``choosable_funds``, the
    single list BE-10 (OBT-471) narrows when it retires one, so *shown but not selectable*
    is enforced here and not only rendered — a fund missing from that list is refused with
    the same message an unknown id gets, because from this endpoint's side they are the
    same fact: it is not on offer.

    **Swapping the fund of an approved request moves both balances in one transaction.**
    The card is already committed against the old fund, so the swap is a compensating
    movement there and a fresh ``APPROVAL_DEDUCTION`` here — the ledger is append-only and
    an approval is never rewritten. The amount is **copied from the movement being
    reversed** and never re-read from ``amount_requested``: what the new fund commits is
    exactly what the old one gets back, whatever the request says today, which is the same
    rule ``reverse_movement`` follows and the reason the two funds cannot come out of step.
    Both movements and the column change ride this function's single commit.

    An approved request with no deduction standing moves no money and still swaps: the
    ledger answers what happened, and there is nothing to give back. The fund is not
    unassignable — ``fund_id`` is required — because clearing the fund of a committed card
    would be an un-approval written as an edit, and un-approving is the board's transaction
    with its own movement.

    **Submission is deliberately not a precondition**, unlike a board move. The mesa
    already reads and edits a request the team has not sent (GATE-02 D4), so refusing to
    name its fund would be a stricter rule about a smaller thing; and the state this
    endpoint exists to make reachable is guarded where it matters — approving still runs
    through ``require_assigned_fund``, whenever the fund arrived.

    **Who assigned it, when, and from which fund to which** is a row of
    ``rr_request_field_history`` keyed ``fund_id``: append-only, ``changed_by`` from the
    session, both sides of the change recorded. The trail's general feature is BE-15's
    (OBT-475); this one field is written here because the DoD asks for the record and the
    table BE-02 built is exactly its shape — inventing a second place to keep it would be
    the second source that trail exists to avoid.
    """
    loaded = await get_request(db, request_id, user, app_key)
    request = loaded.request
    previous = request.fund_id

    offered = {fund.id: fund for fund in await choosable_funds(db)}
    if fund_id not in offered:
        raise UnknownReferenceError(f"Not a fund the mesa may assign: {fund_id}")

    if previous == fund_id:
        return FundAssignment(
            request_id=request.id,
            fund_id=fund_id,
            previous_fund_id=previous,
            changed=False,
            assigned_by=user.id,
            assigned_at=None,
            fund_deltas=(),
            movement_ids=(),
        )

    deltas: list[FundMoved] = []
    movement_ids: list[str] = []
    if request.stage is RRStage.APROVADO:
        deduction = await unreversed_deduction(db, request.id)
        if deduction is not None:
            reason = f"Fund reassignment: {deduction.fund_id} -> {fund_id}"
            reversal = await reverse_movement(
                db, movement_id=deduction.id, author_id=user.id, reason=reason
            )
            fresh = await append_movement(
                db,
                fund_id=fund_id,
                kind=RRMovementKind.APPROVAL_DEDUCTION,
                amount=deduction.amount,
                author_id=user.id,
                reason=reason,
                request_id=request.id,
            )
            deltas = [
                FundMoved(fund_id=deduction.fund_id, committed_delta=-reversal.amount),
                FundMoved(fund_id=fund_id, committed_delta=fresh.amount),
            ]
            movement_ids = [reversal.id, fresh.id]

    request.fund_id = fund_id
    history = RRRequestFieldHistory(
        request_id=request.id,
        field_key="fund_id",
        old_value=previous,
        new_value=fund_id,
        changed_by=user.id,
    )
    db.add(history)
    await db.flush()
    await db.refresh(history, ["changed_at"])

    assignment = FundAssignment(
        request_id=request.id,
        fund_id=fund_id,
        previous_fund_id=previous,
        changed=True,
        assigned_by=user.id,
        assigned_at=history.changed_at,
        fund_deltas=tuple(deltas),
        movement_ids=tuple(movement_ids),
    )
    await db.commit()
    return assignment
