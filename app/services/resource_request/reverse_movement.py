from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, UnknownReferenceError, ValidationError
from app.db.models.resource_request import RRFund, RRFundMovement, RRMovementKind


async def reverse_movement(
    db: AsyncSession, *, movement_id: str, author_id: str, reason: str
) -> RRFundMovement:
    """Write the compensating movement for ``movement_id`` — never an UPDATE, by design.

    The ledger is append-only, so undoing is another entry: un-approving restores a fund
    the same way approving deducted from it, and a wrong allocation is corrected the same
    way (GATE-01 D6). Like ``append_movement`` it **flushes and never commits** — the
    caller owns the transaction — and takes the same ``FOR UPDATE`` on the fund row, which
    is also what makes the already-reversed check below decidable: two concurrent
    reversals of one movement serialize there, and the second finds the first's row.

    **A compensation is exact by construction.** Fund, request, amount and currency are
    copied from the movement being reversed rather than accepted as parameters — a caller
    that could state the amount could also mis-state it, and a partial correction is
    written as a full reversal plus a new entry, so every ledger line keeps one meaning.

    **A reversal is not reversed.** Re-applying what a wrong reversal undid is a new
    movement of the original kind, which reads in the history as what actually happened;
    a chain of negations would have to be resolved before any row meant anything.

    ``reason`` is the author's why, carried on the compensating row itself; what it
    reverses is structural, in ``reverses_id``.
    """
    target = (
        await db.execute(select(RRFundMovement).where(RRFundMovement.id == movement_id))
    ).scalar_one_or_none()
    if target is None:
        raise UnknownReferenceError(f"Unknown movement: {movement_id}")
    if target.kind is RRMovementKind.REVERSAL:
        raise ValidationError(
            "A reversal is not reversed — re-enter the original movement instead."
        )

    await db.execute(select(RRFund).where(RRFund.id == target.fund_id).with_for_update())

    already = (
        await db.execute(select(RRFundMovement.id).where(RRFundMovement.reverses_id == movement_id))
    ).first()
    if already:
        raise ConflictError(f"Movement already reversed: {movement_id}")

    movement = RRFundMovement(
        fund_id=target.fund_id,
        request_id=target.request_id,
        kind=RRMovementKind.REVERSAL,
        amount=target.amount,
        currency=target.currency,
        reverses_id=target.id,
        reason=reason,
        created_by=author_id,
    )
    db.add(movement)
    await db.flush()
    return movement
