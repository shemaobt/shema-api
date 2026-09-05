from decimal import Decimal
from typing import NamedTuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.db.models.auth import User
from app.db.models.resource_request import RRStage
from app.services.resource_request._transition import transition_stage
from app.services.resource_request.get_request import get_request


class BoardMoved(NamedTuple):
    """What a move did, as values — read before the commit expires the rows.

    ``moved`` is ``False`` when the card was already in the column: nothing was written,
    which is FE-15's *moved: null* answered decidably rather than as a refusal — asking
    for the state a card is in is not an illegal move. ``committed_delta`` mirrors the
    frontend's ``FundDelta``: positive entering ``aprovado``, negative leaving it,
    ``None`` when no money moved — including a card with no fund leaving a column that
    never committed any.
    """

    request_id: str
    stage: RRStage
    moved: bool
    from_stage: RRStage | None
    transition_id: str | None
    movement_id: str | None
    fund_id: str | None
    committed_delta: Decimal | None


async def move_request(
    db: AsyncSession, request_id: str, to_stage: RRStage, user: User, app_key: str
) -> BoardMoved:
    """The mesa's hand on the board: one card to one column, money effects included.

    The graph across the six columns is total — the decision and its record are in
    ``_transition.py``'s docstring — so what is refused here is a state, not an edge:
    **a draft is not on the board.** A request enters the board by being submitted
    (``submit_request`` says so: every stage change afterwards is this function's), and a
    stage on an unsubmitted row is the column's default, not a position the mesa gave it.
    Moving one would put a document the mesa has never received onto the mesa's board.

    Everything the move does — the deduction entering ``aprovado``, the compensating
    reversal leaving it, the stage event naming the movement — happens in
    ``transition_stage`` under this function's single commit, so the stage and the ledger
    cannot come apart. The answer is captured before that commit because the commit
    expires the rows, and a NamedTuple of values needs no refresh round trip.
    """
    loaded = await get_request(db, request_id, user, app_key)
    request = loaded.request

    if request.submitted_at is None:
        raise ConflictError("This request has not been submitted, so it is not on the board yet.")

    move = await transition_stage(
        db,
        request=request,
        to_stage=to_stage,
        moved_by=user.id,
        reason=f"Board move: {request.stage.value} -> {to_stage.value}",
    )
    if move is None:
        return BoardMoved(
            request_id=request.id,
            stage=request.stage,
            moved=False,
            from_stage=None,
            transition_id=None,
            movement_id=None,
            fund_id=None,
            committed_delta=None,
        )

    moved = BoardMoved(
        request_id=request.id,
        stage=request.stage,
        moved=True,
        from_stage=move.transition.from_stage,
        transition_id=move.transition.id,
        movement_id=move.movement.id if move.movement is not None else None,
        fund_id=move.movement.fund_id if move.movement is not None else None,
        committed_delta=move.committed_delta,
    )
    await db.commit()
    return moved
