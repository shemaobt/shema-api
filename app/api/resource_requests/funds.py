"""Fund and balance reads, and the movement history — the ledger's read surface.

Read-only on purpose. The ledger's writers exist as services (``append_movement``,
``reverse_movement``) and no route here reaches them: who writes an allocation is BE-09's
(OBT-469) with its own capability, and the movements a stage change causes are BE-08's
(OBT-457), inside the transaction that moves the card. A write route added here would be
one of those issues built without its rules.

All three routes gate on ``manage_funds`` — the Painel's entry gate, held by mesa and
Gestor and by no team. The history by request sits on a ``/requests/…`` path but carries
the same gate, not ``edit_requests``: it is money, and GATE-03 D4 gives a team its status
and nothing else.
"""

from fastapi import APIRouter

from app.api.resource_requests._deps import CanManageFunds, Db
from app.models.resource_request import FundOut, MovementOut
from app.services import resource_request as service

router = APIRouter(tags=["resource requests"])


@router.get("/funds")
async def list_funds(user: CanManageFunds, db: Db) -> list[FundOut]:
    """Every fund with alocado, comprometido and disponível, summed on this read."""
    balances = await service.fund_balances(db)
    return [FundOut(**balance._asdict()) for balance in balances]


@router.get("/funds/{fund_id}/movements")
async def fund_movements(fund_id: str, user: CanManageFunds, db: Db) -> list[MovementOut]:
    """One fund's ledger, oldest first."""
    rows = await service.movements_of_fund(db, fund_id)
    return [MovementOut.model_validate(row) for row in rows]


@router.get("/requests/{request_id}/movements")
async def request_movements(request_id: str, user: CanManageFunds, db: Db) -> list[MovementOut]:
    """Every movement a request caused, oldest first, whichever fund it touched."""
    rows = await service.movements_of_request(db, request_id)
    return [MovementOut.model_validate(row) for row in rows]
