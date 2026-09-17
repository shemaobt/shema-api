"""The fund's whole surface: the balance reads, the ledger history, and its life cycle.

The reads came first and are still read-only about **money**. The ledger's writers exist
as services (``append_movement``, ``reverse_movement``) and no route here reaches them:
who writes an allocation is BE-09's (OBT-469) with its own capability, and the movements a
stage change causes are BE-08's (OBT-457), inside the transaction that moves the card. A
route here that moved money would be one of those issues built without its rules.

What BE-10 (OBT-471) adds writes the fund's **identity** and never its balance — create,
rename, retire. All four of the new routes gate on ``administer_funds``, held by the
Gestor alone: GATE-01 D1 left four names undecided and the client answered that the Gestor
types them, so the capability is one of control, beside ``assign_fund`` and
``allocate_funds``, and not beside ``manage_funds``, which is the Painel's door and which
the whole mesa holds.

The reads keep ``manage_funds`` for the reason they always had it — the Painel's cards are
the mesa's screen too, and a balance the mesa cannot read is a panel with a hole in it.

Retirement is ``POST /funds/{id}/retirement`` and deliberately not ``DELETE /funds/{id}``.
A fund the ledger cites can never be deleted, and a ``DELETE`` that does not delete is a
verb promising the caller something the server will not do.

``/funds/reserved-names`` is a literal path beside ``/funds/{fund_id}/…`` and cannot
collide with it: no fund id is ``reserved-names``, since every id is 32 hex characters
minted by ``create_fund`` — and the one inherited id is ``linguas``.
"""

from fastapi import APIRouter, status

from app.api.resource_requests._deps import CanAdministerFunds, CanManageFunds, Db
from app.models.resource_request import FundAdminOut, FundNameIn, FundOut, MovementOut
from app.services import resource_request as service

router = APIRouter(tags=["resource requests"])


@router.get("/funds")
async def list_funds(user: CanManageFunds, db: Db) -> list[FundOut]:
    """Every fund with alocado, comprometido and disponível, summed on this read.

    Retired funds are here too, flagged. Their money is money the ledger holds, and the
    list of choice is this list filtered on ``retired`` — never this list shortened.
    """
    balances = await service.fund_balances(db)
    return [FundOut(**balance._asdict()) for balance in balances]


@router.get("/funds/reserved-names")
async def reserved_fund_names(user: CanAdministerFunds) -> list[str]:
    """The four names GATE-01 left undecided, offered to the Gestor who will decide them.

    Names, not funds: nothing here is a row, nothing here is reserved in the database, and
    creating one is an ordinary creation that can be refused for a name already taken.
    """
    return list(service.RESERVED_FUND_NAMES)


@router.post("/funds", status_code=status.HTTP_201_CREATED)
async def create_fund(payload: FundNameIn, user: CanAdministerFunds, db: Db) -> FundAdminOut:
    """Mint a fund from a name. The id is the server's and never the payload's."""
    fund = await service.create_fund(db, name=payload.name)
    return FundAdminOut.model_validate(fund)


@router.patch("/funds/{fund_id}")
async def rename_fund(
    fund_id: str, payload: FundNameIn, user: CanAdministerFunds, db: Db
) -> FundAdminOut:
    """Change what the fund is called. ``PATCH`` because the name is the only field there
    is to state, and the id in the path is the one thing this call cannot move."""
    fund = await service.rename_fund(db, fund_id=fund_id, name=payload.name)
    return FundAdminOut.model_validate(fund)


@router.post("/funds/{fund_id}/retirement")
async def retire_fund(fund_id: str, user: CanAdministerFunds, db: Db) -> FundAdminOut:
    """End the fund: out of the list of choice, still in every line of the ledger.

    Answers 409 while requests on this fund are still undecided, with their count.
    """
    fund = await service.retire_fund(db, fund_id=fund_id)
    return FundAdminOut.model_validate(fund)


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
