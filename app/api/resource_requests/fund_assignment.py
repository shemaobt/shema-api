"""Which fund a request draws from: the mesa's triage decision, and the selector for it.

Both routes gate on ``assign_fund`` — **mesa-only**, GATE-01 D4 asked directly and the
client re-answered *"somente a mesa"* on 28/aug/2026. That is why the gate is not
``manage_funds``, which the Gestor also holds and which is the Painel's entry: a Gestor
session reaching either of these gets a 403, and it is the client's sentence rather than a
restrictive default of ours.

It is a router of its own rather than two more handlers in ``funds.py``, whose docstring
declares that file read-only: the ledger's writers live behind the issues that own their
rules, and this is one of those writers arriving with its own.

The rule this endpoint exists to make satisfiable — a request does not enter ``aprovado``
with ``fund_id IS NULL`` — is *not* here. It has one owner,
``app/services/resource_request/_fund_assignment.py``, and both approval doors read it
through ``guard_stage_entry``.
"""

from fastapi import APIRouter

from app.api.resource_requests._deps import APP_KEY, CanAssignFund, Db
from app.models.resource_request import (
    FundAssignmentIn,
    FundAssignmentOut,
    FundDeltaOut,
    FundOptionOut,
)
from app.services import resource_request as service
from app.services.resource_request.assign_fund import FundAssignment

router = APIRouter(tags=["resource requests"])


def _out(assignment: FundAssignment) -> FundAssignmentOut:
    return FundAssignmentOut(
        request_id=assignment.request_id,
        fund_id=assignment.fund_id,
        previous_fund_id=assignment.previous_fund_id,
        changed=assignment.changed,
        assigned_by=assignment.assigned_by,
        assigned_at=assignment.assigned_at,
        fund_deltas=[FundDeltaOut(**delta._asdict()) for delta in assignment.fund_deltas],
        movement_ids=list(assignment.movement_ids),
    )


@router.put("/requests/{request_id}/fund")
async def assign_fund(
    request_id: str, assignment: FundAssignmentIn, user: CanAssignFund, db: Db
) -> FundAssignmentOut:
    """Set or change the request's fund — with both balances, transactionally, when it is
    already approved.

    ``PUT`` because the fund is one value and writing it twice with the same id changes
    nothing: the second call answers ``changed: false`` and writes neither a history row
    nor a movement.
    """
    return _out(await service.assign_fund(db, request_id, assignment.fund_id, user, APP_KEY))


@router.get("/requests/{request_id}/fund-options")
async def fund_options(request_id: str, user: CanAssignFund, db: Db) -> list[FundOptionOut]:
    """The funds the mesa may assign here, plus this request's own if it was retired."""
    options = await service.fund_options(db, request_id, user, APP_KEY)
    return [FundOptionOut(**option._asdict()) for option in options]
