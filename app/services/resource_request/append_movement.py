from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UnknownReferenceError, ValidationError
from app.db.models.resource_request import RRFund, RRFundMovement, RRMovementKind

_CENT = Decimal("0.01")
_MONEY_LIMIT = Decimal(10) ** 12


async def append_movement(
    db: AsyncSession,
    *,
    fund_id: str,
    kind: RRMovementKind,
    amount: Decimal,
    author_id: str,
    reason: str,
    request_id: str | None = None,
) -> RRFundMovement:
    """Append one entry to the ledger, serialized on the fund row it moves.

    **It flushes and never commits.** The caller owns the transaction, and that is the
    contract BE-08 (OBT-457) is built on: a stage change and the movement it causes commit
    or roll back together, which is only possible if this function does not close the
    transaction under it. The lock taken here lives exactly as long as that transaction.

    **The ``FOR UPDATE`` on the fund row is what GATE-01 D5 did not relax.** With balances
    as sums, two concurrent inserts lose nothing — the lock is not protecting the ledger
    from a lost write. What it protects is the *reading* beside the write: the warning D5
    chose over a refusal is computed from the balance, and without serialization two
    approvals against one fund each see the sum before the other, so neither warns. Locked,
    the second computes its sum after the first is visible and gets the decidable answer —
    *both succeed, and the total is right* (design §7.3). On SQLite the clause compiles to
    nothing, silently, which is why the test for this lives behind a PostgreSQL URL.

    ``author_id`` comes from the bearer token and never from a payload; for an
    ``ALLOCATION`` this row's ``created_by``/``created_at``/``reason`` *are* GATE-01 D6's
    "who edited it and when" — the reason ``rr_funds`` has no ``allocated`` column.

    A reversal is refused here rather than accepted with extra care: a compensating
    movement copies what it compensates, so it has its own writer, ``reverse_movement``,
    and a kind parameter that could also mean *reversal* would let a caller invent the
    amount a compensation is precisely not allowed to invent.

    ``currency`` is deliberately not a parameter. The column keeps its ``BRL`` default;
    whether an approval writes the request's own currency is BE-08's call, and a balance
    summed over two currencies is a question nobody has answered — not one to freeze in a
    signature here.

    The amount is refused where it does not fit ``Numeric(14, 2)``, the same rule BE-05
    applies to payloads and for the ledger's own reason: PostgreSQL rounds a sub-cent
    value into the column while SQLite stores it as sent, so a movement written unchecked
    would sum differently per dialect. ``is_finite`` comes first because a ``NaN``
    *comparison* raises ``InvalidOperation`` — the ``quantize`` lesson of design §8.5,
    one operator earlier. Checked before the lock: a refusal takes no lock at all.
    """
    if kind is RRMovementKind.REVERSAL:
        raise ValidationError(
            "A reversal names the movement it compensates — use reverse_movement."
        )
    if not amount.is_finite():
        raise ValidationError(f"Not an amount of money: {amount}")
    if amount <= 0:
        raise ValidationError(f"A movement moves money, and {amount} moves none.")
    if abs(amount) >= _MONEY_LIMIT or amount != amount.quantize(_CENT):
        raise ValidationError(f"Does not fit the ledger's Numeric(14, 2): {amount}")

    fund = (
        await db.execute(select(RRFund).where(RRFund.id == fund_id).with_for_update())
    ).scalar_one_or_none()
    if fund is None:
        raise UnknownReferenceError(f"Unknown fund: {fund_id}")

    movement = RRFundMovement(
        fund_id=fund_id,
        request_id=request_id,
        kind=kind,
        amount=amount,
        reason=reason,
        created_by=author_id,
    )
    db.add(movement)
    await db.flush()
    return movement
