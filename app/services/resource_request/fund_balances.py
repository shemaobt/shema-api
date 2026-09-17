from decimal import Decimal
from typing import NamedTuple

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.db.models.resource_request import RRFund, RRFundMovement, RRMovementKind

_ZERO = Decimal("0.00")


class FundBalance(NamedTuple):
    id: str
    name: str
    retired: bool
    allocated: Decimal
    committed: Decimal
    available: Decimal


async def fund_balances(db: AsyncSession) -> list[FundBalance]:
    """Every fund with its three figures — two summed over the ledger, one derived.

    *Alocado* is the allocations minus their reversals; *comprometido* is the commitments
    and approval deductions minus theirs; *disponível* is their difference, computed here
    and nowhere stored — store two, derive the third (contract §3.2). A reversal counts
    against the bucket of the movement it reverses, which the self-join reads off
    ``reverses_id`` rather than off a sign convention every writer would have to share.

    The sums happen in the database because balances *are* queries (design §7.1); this
    function only names the buckets. A fund with no movements answers three zeros — the
    state every fund is born in since GATE-01 D6 — and a negative *disponível* is a valid
    answer, not an error: D5 chose a warning over a refusal, and the refusal shape this
    module deliberately does not have starts with a balance read that cannot go negative.

    **Retired funds are listed, not filtered** (BE-10, OBT-471). What retirement takes
    away is being chosen, and dropping the fund from this read would take away something
    else: its *comprometido* would leave the Painel while the ledger still holds it, so
    money already promised would disappear from the only screen that shows it. ``retired``
    travels instead, and the list of choice is the subset a caller filters on it.

    Callable inside the transaction that holds a fund's ``FOR UPDATE`` lock, which is how
    BE-08 computes the warning against a sum that is not moving under it.
    """
    reversed_movement = aliased(RRFundMovement)
    bucket = case(
        (RRFundMovement.kind == RRMovementKind.REVERSAL, reversed_movement.kind),
        else_=RRFundMovement.kind,
    )
    signed = case(
        (RRFundMovement.kind == RRMovementKind.REVERSAL, -RRFundMovement.amount),
        else_=RRFundMovement.amount,
    )
    sums = (
        await db.execute(
            select(RRFundMovement.fund_id, bucket, func.sum(signed))
            .outerjoin(reversed_movement, RRFundMovement.reverses_id == reversed_movement.id)
            .group_by(RRFundMovement.fund_id, bucket)
        )
    ).all()

    by_fund: dict[str, dict[RRMovementKind, Decimal]] = {}
    for fund_id, kind, total in sums:
        by_fund.setdefault(fund_id, {})[RRMovementKind(kind)] = Decimal(total)

    funds = (await db.execute(select(RRFund).order_by(RRFund.id))).scalars().all()

    balances: list[FundBalance] = []
    for fund in funds:
        buckets = by_fund.get(fund.id, {})
        allocated = buckets.get(RRMovementKind.ALLOCATION, _ZERO)
        committed = buckets.get(RRMovementKind.COMMITMENT, _ZERO) + buckets.get(
            RRMovementKind.APPROVAL_DEDUCTION, _ZERO
        )
        balances.append(
            FundBalance(
                id=fund.id,
                name=fund.name,
                retired=fund.retired_at is not None,
                allocated=allocated,
                committed=committed,
                available=allocated - committed,
            )
        )
    return balances
