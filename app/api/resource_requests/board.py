"""Stage transitions on the wire: the mesa's hand on the board, and the board's trail.

The move gates on ``move_board`` — mesa and Gestor since GATE-02 D3 (*"tem acesso a quase
tudo em relação aos projetos"*), never the team — and the history gates on
``manage_funds``, the Painel's entry gate, the same reasoning ``funds.py`` records: the
trail is a Painel read, and GATE-03 D4 gives a team its status and nothing else. Today
the two gates admit the same two roles; they are still two gates because they answer two
questions, and BE-16's fourth role is exactly the kind of arrival that splits them.

The graph and its refusals live in ``app/services/resource_request/_transition.py``,
where both writers converge — this file parses, calls one service and shapes the answer,
like every router in the module.
"""

from fastapi import APIRouter

from app.api.resource_requests._deps import APP_KEY, CanManageFunds, CanMoveBoard, Db
from app.models.resource_request import BoardMoveIn, BoardMoveOut, FundDeltaOut, TransitionOut
from app.services import resource_request as service
from app.services.resource_request.move_request import BoardMoved

router = APIRouter(tags=["resource requests"])


def _out(moved: BoardMoved) -> BoardMoveOut:
    fund_delta = None
    if moved.committed_delta is not None and moved.fund_id is not None:
        fund_delta = FundDeltaOut(fund_id=moved.fund_id, committed_delta=moved.committed_delta)
    return BoardMoveOut(
        request_id=moved.request_id,
        stage=moved.stage,
        moved=moved.moved,
        from_stage=moved.from_stage,
        transition_id=moved.transition_id,
        movement_id=moved.movement_id,
        fund_delta=fund_delta,
    )


@router.post("/requests/{request_id}/move")
async def move_request(
    request_id: str, move: BoardMoveIn, user: CanMoveBoard, db: Db
) -> BoardMoveOut:
    """One card to one column — with the deduction or the restoration, transactionally.

    Mover and instant come from the session and the server clock; a card already in the
    column answers ``moved: false`` and writes nothing.
    """
    return _out(await service.move_request(db, request_id, move.to, user, APP_KEY))


@router.get("/requests/{request_id}/transitions")
async def request_transitions(request_id: str, user: CanManageFunds, db: Db) -> list[TransitionOut]:
    """The request's board history, oldest first — decisions and drags, told apart."""
    rows = await service.transitions_of_request(db, request_id)
    return [TransitionOut.model_validate(row) for row in rows]
