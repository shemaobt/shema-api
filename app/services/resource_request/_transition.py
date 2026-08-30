"""The one path every stage change takes — a decision's move and a hand's drag alike.

GATE-02 D6 made recording a decision move the card, and BE-08 (OBT-457) gives the mesa's
hand the same power over the same six columns. The corruption this module exists to
prevent is a stage that changed without its deduction, or a deduction without its stage —
so both writers go through ``transition_stage``, which writes the ledger effect and the
stage event together, **flushes and never commits**. The caller owns the transaction,
which is what makes the two writes one fate: ``save_evaluation`` commits a decision, its
scores, the movement and the move under one commit, and ``move_request`` does the same
for a drag.

**The graph is total, and that is a decision with a record rather than a default.** The
export drags any column to any column, FE-15 kept the pure transition total on purpose —
*"apertá-lo aqui congelaria em código uma decisão que é da mesa"* — and GATE-02 D6's own
reading is that the mesa may drag a card it never evaluated, a decided card included: a
decision implies a column, a column never implies a decision, and dragging out of
``aprovado`` is precisely how an approval is undone (its compensating movement rides the
same transaction). What is refused is not an edge of the graph but a state of the
request: a draft is not on the board (``move_request``), and nothing enters ``aprovado``
without a fund and an amount to deduct — GATE-01 D4's invariant, BE-11's rule, fired
here because this is the transition it guards. Deliberately a service rule and **not** a
DDL CHECK: the same ``NULL`` is legitimate one column earlier.

**The ledger effect is the export's golden rule, as movements.** Only ``aprovado``
commits funds: entering it appends an ``APPROVAL_DEDUCTION`` for the request's
``amount_requested``, leaving it reverses that deduction — the compensating movement
copies the amount from the movement it undoes, so un-approving restores exactly what
approving deducted, whatever the request says today. Moves between the other five
columns move no money, ``condicional`` included. Leaving ``aprovado`` with no unreversed
deduction on record restores nothing rather than inventing an amount: the ledger answers
what actually happened, and a card that never deducted has nothing to give back.
"""

from decimal import Decimal
from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.db.models.resource_request import (
    RRBoardTransition,
    RRFundMovement,
    RRMovementKind,
    RRRequest,
    RRStage,
)
from app.services.resource_request.append_movement import append_movement
from app.services.resource_request.reverse_movement import reverse_movement


class StageMove(NamedTuple):
    transition: RRBoardTransition
    movement: RRFundMovement | None
    committed_delta: Decimal | None


def guard_stage_entry(request: RRRequest, to_stage: RRStage) -> tuple[str, Decimal] | None:
    """What entering ``aprovado`` will deduct — or a refusal, before anything is written.

    Answers ``None`` when the change does not enter ``aprovado`` (a move elsewhere, or a
    no-op already there), and the ``(fund_id, amount)`` the deduction will move when it
    does. Callable with nothing written yet, which is why ``save_evaluation`` runs it in
    its pre-check phase: a refusal must leave nothing half-saved, and a session that
    flushed before being refused shows its pending rows to whoever shares it.
    """
    if to_stage is not RRStage.APROVADO or request.stage is RRStage.APROVADO:
        return None
    if request.fund_id is None:
        raise ConflictError(
            "A request does not enter aprovado with no fund: "
            "the mesa assigns one at triage before approving."
        )
    if request.amount_requested is None:
        raise ConflictError("A request does not enter aprovado with no amount requested.")
    return (request.fund_id, request.amount_requested)


async def _unreversed_deduction(db: AsyncSession, request_id: str) -> RRFundMovement | None:
    """The deduction still standing for this request — at most one by construction.

    Entering ``aprovado`` twice without leaving is impossible (a same-stage change is a
    no-op), so deductions and reversals alternate; the newest is read defensively rather
    than assumed alone.
    """
    reversed_ids = select(RRFundMovement.reverses_id).where(RRFundMovement.reverses_id.is_not(None))
    stmt = (
        select(RRFundMovement)
        .where(
            RRFundMovement.request_id == request_id,
            RRFundMovement.kind == RRMovementKind.APPROVAL_DEDUCTION,
            RRFundMovement.id.not_in(reversed_ids),
        )
        .order_by(RRFundMovement.created_at.desc(), RRFundMovement.id.desc())
    )
    return (await db.execute(stmt)).scalars().first()


async def transition_stage(
    db: AsyncSession,
    *,
    request: RRRequest,
    to_stage: RRStage,
    moved_by: str,
    reason: str,
    evaluation_id: str | None = None,
) -> StageMove | None:
    """Move one card, with whatever the move does to money, in the caller's transaction.

    ``None`` when the card is already in the column — nothing is written, which is
    FE-15's *moved: null* and what lets a decision land on a card the mesa already
    dragged there without deducting twice (GATE-02 D6 converging with the manual move).

    The write order is the FK's, not taste: the movement first, because the stage event
    names it through ``rr_board_transitions.movement_id``; then the event and the stage,
    one flush. ``append_movement`` and ``reverse_movement`` both take the fund row's
    ``FOR UPDATE`` and never commit, so two concurrent approvals serialize there and this
    function closes no transaction under its caller.

    ``evaluation_id`` says a decision caused this move; a hand's drag leaves it ``None``.
    """
    if request.stage is to_stage:
        return None

    claim = guard_stage_entry(request, to_stage)

    movement: RRFundMovement | None = None
    committed_delta: Decimal | None = None
    if claim is not None:
        fund_id, amount = claim
        movement = await append_movement(
            db,
            fund_id=fund_id,
            kind=RRMovementKind.APPROVAL_DEDUCTION,
            amount=amount,
            author_id=moved_by,
            reason=reason,
            request_id=request.id,
        )
        committed_delta = movement.amount
    elif request.stage is RRStage.APROVADO:
        deduction = await _unreversed_deduction(db, request.id)
        if deduction is not None:
            movement = await reverse_movement(
                db, movement_id=deduction.id, author_id=moved_by, reason=reason
            )
            committed_delta = -movement.amount

    transition = RRBoardTransition(
        request_id=request.id,
        from_stage=request.stage,
        to_stage=to_stage,
        moved_by=moved_by,
        movement_id=movement.id if movement is not None else None,
        evaluation_id=evaluation_id,
    )
    db.add(transition)
    request.stage = to_stage
    await db.flush()
    return StageMove(transition=transition, movement=movement, committed_delta=committed_delta)
