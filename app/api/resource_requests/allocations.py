"""The alocado on the wire: the Gestor's write path and the read FE-26 renders (BE-09).

The write gates on ``allocate_funds`` and never ``manage_funds`` — GATE-01 D6 gave the
allocated value to the Gestor alone, and ``manage_funds`` is the Painel's door, which the
mesa also holds; guarding the write with the door would hand allocation to the whole mesa.
The read stays on ``manage_funds`` like every other fund read in ``funds.py``: the card
line saying who allocated is Painel surface, and hiding it from the mesa would make the
one number on their own panel anonymous.

``PUT`` because the edit states the field's value and saying it twice changes nothing —
what each save writes into the ledger is ``set_allocation``'s translation, and the
lançamento of the issue's title is that translation's output, not this route's input.
"""

from fastapi import APIRouter

from app.api.resource_requests._deps import CanAllocateFunds, CanManageFunds, Db
from app.models.resource_request import AllocationIn, AllocationOut
from app.services import resource_request as service

router = APIRouter(tags=["resource requests"])


@router.get("/funds/{fund_id}/allocation")
async def read_allocation(fund_id: str, user: CanManageFunds, db: Db) -> AllocationOut:
    """The alocado summed over the ledger, with who last put it there and when."""
    allocation = await service.allocation_of_fund(db, fund_id)
    return AllocationOut(**allocation._asdict())


@router.put("/funds/{fund_id}/allocation")
async def set_allocation(
    fund_id: str, payload: AllocationIn, user: CanAllocateFunds, db: Db
) -> AllocationOut:
    """Set the alocado to the stated value, written as ledger entries and nothing else."""
    allocation = await service.set_allocation(
        db,
        fund_id=fund_id,
        amount=payload.amount,
        author_id=user.id,
        reason=payload.reason,
    )
    return AllocationOut(**allocation._asdict())
