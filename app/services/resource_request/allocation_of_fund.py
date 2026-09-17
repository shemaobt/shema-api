from datetime import datetime
from decimal import Decimal
from typing import NamedTuple

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.exceptions import NotFoundError
from app.db.models.auth import User
from app.db.models.resource_request import RRFund, RRFundMovement, RRMovementKind
from app.services.resource_request.fund_balances import fund_balances


class FundAllocation(NamedTuple):
    fund_id: str
    allocated: Decimal
    allocated_by: str | None
    allocated_at: datetime | None


async def allocation_of_fund(db: AsyncSession, fund_id: str) -> FundAllocation:
    """The alocado as FE-26 renders it: the summed value plus D6's who-and-when mark.

    *Alocado* is ``fund_balances``' own sum — read through it rather than re-summed, so
    the reversal-bucket rule keeps one implementation — and the mark is the authorship of
    the **latest movement that touched that bucket**: an ``ALLOCATION``, or a reversal of
    one. Reversals count because a correction down to zero writes only reversals, and a
    mark that skipped them would name the Gestor whose entry was just corrected away —
    the opposite of GATE-01 D6's "who edited it and when".

    ``allocated_by`` is the author's **e-mail**, not the user id ``MovementOut`` carries:
    this read exists for a card line ("alocado por … em …"), and the e-mail is the one
    identifier the frontend has ever held for a person (its ``fundStore`` stores exactly
    that). The ledger's own history keeps the id, as forensics should.

    A fund nobody has allocated answers ``0.00`` with no mark at all — the state every
    fund is born in since D6, and the same rule the frontend's sparse store follows:
    stamping a name on a value nobody entered would be fabricated authorship.
    """
    fund = (await db.execute(select(RRFund.id).where(RRFund.id == fund_id))).scalar_one_or_none()
    if fund is None:
        raise NotFoundError(f"Fund not found: {fund_id}")

    balances = {balance.id: balance for balance in await fund_balances(db)}
    allocated = balances[fund_id].allocated

    reversed_movement = aliased(RRFundMovement)
    last_touch = (
        await db.execute(
            select(RRFundMovement.created_at, User.email)
            .join(User, User.id == RRFundMovement.created_by)
            .outerjoin(reversed_movement, RRFundMovement.reverses_id == reversed_movement.id)
            .where(
                RRFundMovement.fund_id == fund_id,
                or_(
                    RRFundMovement.kind == RRMovementKind.ALLOCATION,
                    reversed_movement.kind == RRMovementKind.ALLOCATION,
                ),
            )
            .order_by(RRFundMovement.created_at.desc(), RRFundMovement.id.desc())
            .limit(1)
        )
    ).first()

    if last_touch is None:
        return FundAllocation(fund_id, allocated, None, None)
    return FundAllocation(fund_id, allocated, last_touch.email, last_touch.created_at)
