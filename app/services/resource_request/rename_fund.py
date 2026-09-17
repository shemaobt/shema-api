from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.db.models.resource_request import RRFund


async def rename_fund(db: AsyncSession, *, fund_id: str, name: str) -> RRFund:
    """Change what a fund is called, and nothing else.

    **The id does not move**, which is the whole reason it is opaque: every ledger entry,
    every request and every board card names the fund by id, and a rename that touched it
    would be a data migration wearing a text field's clothes. Nothing here writes
    ``fund_id`` anywhere — not on the row, not on a movement, not on a request — and that
    absence is the DoD's *"nenhum ``fund_id`` é remendado"*.

    The same uniqueness check ``create_fund`` runs, for the same reason and with one
    addition: a fund renamed to the name it already has is not a duplicate of itself. It
    is also not an edit, but it is not refused either — the caller stated the field's
    value, and saying it twice changing nothing is the ``PUT``-shaped honesty
    ``set_allocation`` already keeps.

    A retired fund can still be renamed. Its name is a label on history rather than an
    option on a screen, and a typo in a label is worth fixing; what retirement takes away
    is being chosen, which is ``retired_at``'s job and not this function's.

    Who renamed it is not written here. That is an edit like any other and belongs to
    BE-15's (OBT-475) trail — a second authorship design standing up in this table is what
    the model's own docstring refuses, and it refuses it for allocation and for renaming
    alike.
    """
    cleaned = name.strip()
    if not cleaned:
        raise ValidationError("A fund needs a name: it is the only identity of it anyone sees.")

    fund = (await db.execute(select(RRFund).where(RRFund.id == fund_id))).scalar_one_or_none()
    if fund is None:
        raise NotFoundError(f"Fund not found: {fund_id}")

    taken = (
        await db.execute(select(RRFund.id).where(RRFund.name == cleaned, RRFund.id != fund_id))
    ).scalar_one_or_none()
    if taken is not None:
        raise ConflictError(f"A fund is already called {cleaned!r}.")

    fund.name = cleaned
    await db.commit()
    await db.refresh(fund)
    return fund
