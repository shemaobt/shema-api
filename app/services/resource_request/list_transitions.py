from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.resource_request import RRBoardTransition, RRRequest


async def transitions_of_request(db: AsyncSession, request_id: str) -> list[RRBoardTransition]:
    """One request's board history, oldest first — the mesa's trail of who moved what.

    Every row answers *quem moveu o quê, quando, de onde para onde*, and two nullable
    columns say why: ``evaluation_id`` names the decision that caused a move (a hand's
    drag carries none — GATE-02 D6's asymmetry, kept legible), ``movement_id`` names the
    ledger entry the move wrote (only onto or off ``aprovado``). Oldest first because a
    history is read in the order it happened, the same rule the ledger reads by.

    An unknown id answers 404 rather than an empty list — for an internal surface a card
    that never moved and a mistyped id are different situations. No row scoping, like
    ``movements_of_fund``: the route gates on ``manage_funds``, whose holders reach every
    request, and GATE-03 D4 keeps a team at its status and away from the board.
    """
    request = (
        await db.execute(select(RRRequest.id).where(RRRequest.id == request_id))
    ).scalar_one_or_none()
    if request is None:
        raise NotFoundError(f"Request not found: {request_id}")

    return list(
        (
            await db.execute(
                select(RRBoardTransition)
                .where(RRBoardTransition.request_id == request_id)
                .order_by(RRBoardTransition.created_at, RRBoardTransition.id)
            )
        )
        .scalars()
        .all()
    )
