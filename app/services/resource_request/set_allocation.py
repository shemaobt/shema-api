from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.db.models.resource_request import RRFund, RRFundMovement, RRMovementKind
from app.services.resource_request.allocation_of_fund import FundAllocation, allocation_of_fund
from app.services.resource_request.append_movement import append_movement
from app.services.resource_request.fund_balances import fund_balances
from app.services.resource_request.reverse_movement import reverse_movement


async def set_allocation(
    db: AsyncSession, *, fund_id: str, amount: Decimal, author_id: str, reason: str
) -> FundAllocation:
    """Make the fund's alocado equal ``amount``, by ledger entries and nothing else.

    GATE-01 D6's "campo editável" is the screen; here the Gestor's edit becomes postings
    in BE-07's append-only ledger, and *who and when* is their own authorship. The value
    is taken as **what the field says, never a delta** — the screen shows a total and the
    Gestor states the new one — and the difference decides what is written:

    - **raised**: one ``ALLOCATION`` of the difference, the lançamento of the title;
    - **lowered**: the correction path — every standing allocation is reversed
      (``reverses_id`` naming each) and the stated value re-entered whole, which is
      ``reverse_movement``'s own "a partial correction is a full reversal plus a new
      entry". No path updates a movement.
    - **unchanged**: nothing. Zero on a newborn fund lands here, and it is valid because
      zero is the state every fund is born in (D6) — while writing an authored movement
      that moved nothing would fabricate an edit, which is also why ``append_movement``'s
      zero refusal stays untouched.

    A negative alocado is refused before anything is read: the field states money put
    into a fund, and no answer of ``fund_balances`` can make a negative one right. The
    wire meets this rule earlier, as ``AllocationIn``'s field-level 422; here it guards
    the callers that do not come through the wire.

    Unlike the two writers it composes, this **is** the operation, so it commits — the
    FE-24 draft-store reasoning inverted: a partial correction left uncommitted would be
    the caller's to finish, and no caller owns more of this edit than the edit itself.
    The fund row's ``FOR UPDATE`` is taken before the balance is read, so two Gestores
    editing at once serialize and the second computes its difference against the first's
    committed sum, never against a sum that is moving under it.
    """
    if amount < 0:
        raise ValidationError(f"An alocado states money put in, and {amount} is less than none.")

    fund = (
        await db.execute(select(RRFund).where(RRFund.id == fund_id).with_for_update())
    ).scalar_one_or_none()
    if fund is None:
        raise NotFoundError(f"Fund not found: {fund_id}")

    balances = {balance.id: balance for balance in await fund_balances(db)}
    current = balances[fund_id].allocated

    if amount > current:
        await append_movement(
            db,
            fund_id=fund_id,
            kind=RRMovementKind.ALLOCATION,
            amount=amount - current,
            author_id=author_id,
            reason=reason,
        )
    elif amount < current:
        reversal_targets = select(RRFundMovement.reverses_id).where(
            RRFundMovement.reverses_id.is_not(None)
        )
        standing = (
            (
                await db.execute(
                    select(RRFundMovement.id)
                    .where(
                        RRFundMovement.fund_id == fund_id,
                        RRFundMovement.kind == RRMovementKind.ALLOCATION,
                        RRFundMovement.id.not_in(reversal_targets),
                    )
                    .order_by(RRFundMovement.created_at, RRFundMovement.id)
                )
            )
            .scalars()
            .all()
        )
        for movement_id in standing:
            await reverse_movement(db, movement_id=movement_id, author_id=author_id, reason=reason)
        if amount > 0:
            await append_movement(
                db,
                fund_id=fund_id,
                kind=RRMovementKind.ALLOCATION,
                amount=amount,
                author_id=author_id,
                reason=reason,
            )

    await db.commit()
    return await allocation_of_fund(db, fund_id)
