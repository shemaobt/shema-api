"""The movement history, by the two axes the ledger answers to.

One operation — read the ledger — asked from the two sides the DoD names: a fund's whole
history (what the Painel's cards stand on) and one request's (what happened to this money).
Both read oldest first, because a ledger is read in the order it was written: a reversal
after the movement it reverses, an allocation before what it funded.

Unknown ids answer 404 rather than an empty list — for an internal money surface an empty
history and a mistyped id are different situations, and the second must not read as the
first. No row scoping: the routes are gated on ``manage_funds``, whose holders reach every
request (``_scope.py``), and GATE-03 D4 keeps a team away from the ledger entirely.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.resource_request import RRFund, RRFundMovement, RRRequest


async def movements_of_fund(db: AsyncSession, fund_id: str) -> list[RRFundMovement]:
    """One fund's ledger, oldest first."""
    fund = (await db.execute(select(RRFund.id).where(RRFund.id == fund_id))).scalar_one_or_none()
    if fund is None:
        raise NotFoundError(f"Fund not found: {fund_id}")

    return list(
        (
            await db.execute(
                select(RRFundMovement)
                .where(RRFundMovement.fund_id == fund_id)
                .order_by(RRFundMovement.created_at, RRFundMovement.id)
            )
        )
        .scalars()
        .all()
    )


async def movements_of_request(db: AsyncSession, request_id: str) -> list[RRFundMovement]:
    """Every movement a request caused, oldest first, whichever fund it touched."""
    request = (
        await db.execute(select(RRRequest.id).where(RRRequest.id == request_id))
    ).scalar_one_or_none()
    if request is None:
        raise NotFoundError(f"Request not found: {request_id}")

    return list(
        (
            await db.execute(
                select(RRFundMovement)
                .where(RRFundMovement.request_id == request_id)
                .order_by(RRFundMovement.created_at, RRFundMovement.id)
            )
        )
        .scalars()
        .all()
    )
