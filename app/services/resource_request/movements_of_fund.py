from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.resource_request import RRFund, RRFundMovement


async def movements_of_fund(db: AsyncSession, fund_id: str) -> list[RRFundMovement]:
    """One fund's ledger, oldest first — a ledger is read in the order it was written.

    Rows sharing a timestamp fall back to id, which is stable rather than meaningful:
    ``created_at`` is the server's stamp, and two movements of one transaction share it.

    An unknown fund answers 404 rather than an empty list — for an internal money surface
    an empty history and a mistyped id are different situations, and the second must not
    read as the first. No row scoping: the route gates on ``manage_funds``, whose holders
    reach every request (``_scope.py``), and GATE-03 D4 keeps a team away from the ledger
    entirely.
    """
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
