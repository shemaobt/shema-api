from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.db.models.resource_request import RRFund, RRRequest, RRStage

#: The two columns a request sits in before anybody has decided about it. The four that
#: follow — ``aprovado``, ``condicional``, ``revisar``, ``recusado`` — are the board face
#: of Parte C's four decisions (contract §2.3), so a card outside these two has been
#: answered and its fund can end without leaving anyone waiting.
UNDECIDED_STAGES: tuple[RRStage, ...] = (RRStage.TRIAGEM, RRStage.ANALISE)


async def retire_fund(db: AsyncSession, *, fund_id: str) -> RRFund:
    """End a fund without deleting it, unless requests are still waiting on it.

    **Retiring never deletes.** ``rr_fund_movements`` holds a foreign key to this row and
    the ledger is append-only, so the money already promised through this fund has to stay
    readable for as long as its movements do. What retirement removes is the fund's place
    in the list of choice; what it keeps is every line of its history. ``retired_at`` says
    both — that it ended, and when — which is the question a movement dated last year
    raises and a boolean could not answer.

    **It refuses with 409 while a request is still undecided on this fund**, and the
    refusal carries the count. Retiring under a live request would leave a team waiting on
    money from a fund that no longer accepts assignment — the mesa would have to notice
    the orphan, and nothing on the board would say so. The count travels because the
    Gestor's next move depends on it: one card is a card to re-point, eleven is a decision
    to postpone. A decided request is not counted, whatever it was decided to be — its
    money is either committed in the ledger, which retirement does not touch, or it is
    never coming, and neither is a reason to keep a fund open.

    Retiring an already retired fund changes nothing and answers the row. The act states
    an end, and an end stated twice is the same end — re-stamping would move the date of
    something that happened earlier, which is the one thing this column must not do.

    Who retired it is BE-15's (OBT-475) trail, for the reason ``rename_fund`` records:
    this table carries no second authorship design.
    """
    fund = (await db.execute(select(RRFund).where(RRFund.id == fund_id))).scalar_one_or_none()
    if fund is None:
        raise NotFoundError(f"Fund not found: {fund_id}")

    if fund.retired_at is not None:
        return fund

    waiting = (
        await db.execute(
            select(func.count())
            .select_from(RRRequest)
            .where(RRRequest.fund_id == fund_id, RRRequest.stage.in_(UNDECIDED_STAGES))
        )
    ).scalar_one()
    if waiting:
        raise ConflictError(
            f"{waiting} request(s) on this fund are still undecided; "
            "decide them or move them to another fund before retiring it."
        )

    fund.retired_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(fund)
    return fund
