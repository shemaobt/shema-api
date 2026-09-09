"""Which funds the mesa may choose from, and what the selector shows beside them.

**Retiring a fund is BE-10's (OBT-471), and it retires by leaving this list.** The client
asked for an area that creates, renames and retires funds; a retired one stops being a
choice and is never deleted, because ``rr_fund_movements`` names it and the ledger is
append-only. So ``choosable_funds`` is the one query BE-10 narrows, and everything that
offers a fund reads it — the selector below and ``assign_fund`` alike, which is what makes
*not selectable* a fact rather than a label the screen is trusted to honour.

**A request already pointing at a retired fund still shows it, marked** (ours, 28/aug/2026).
A selector that dropped it would render an assignment as if it were absent, and the mesa
would read *no fund* on a card whose money is committed against one — the same
fabricated-emptiness the frontend's score badge fixed by separating *unevaluated* from
*zero*. So the assigned fund is carried into the options whether or not it is a choice, and
``selectable`` is what says which of the two it is.

``options_from`` is pure and takes the two lists rather than the session, so the retired
case is testable today: it becomes real the day BE-10 narrows the query, and a rule that
can only be exercised after another issue lands is a rule nobody has run.
"""

from collections.abc import Sequence
from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.resource_request import RRFund


class FundOption(NamedTuple):
    """One row of the mesa's fund selector.

    ``assigned`` is this request's current fund, ``selectable`` says the mesa may still
    choose it, and ``retired`` is the one combination that needs a word of its own: a fund
    that is assigned and is no longer a choice. The three are not one enum because a
    screen renders them as three different things — a checkmark, an enabled control and a
    badge.
    """

    id: str
    name: str
    assigned: bool
    selectable: bool
    retired: bool


async def choosable_funds(db: AsyncSession) -> Sequence[RRFund]:
    """The funds the mesa may assign, by name — BE-10's list, unfiltered until it lands."""
    return (await db.execute(select(RRFund).order_by(RRFund.name))).scalars().all()


def options_from(choosable: Sequence[RRFund], assigned: RRFund | None) -> list[FundOption]:
    """The selector for a request whose fund is ``assigned`` — retired funds included.

    A retired assignment lands **after** the choices rather than among them: it is not one,
    and putting it in the middle of a list the mesa picks from is where a screen ends up
    offering it anyway.
    """
    assigned_id = assigned.id if assigned is not None else None
    options = [
        FundOption(
            id=fund.id,
            name=fund.name,
            assigned=fund.id == assigned_id,
            selectable=True,
            retired=False,
        )
        for fund in choosable
    ]
    if assigned is not None and all(option.id != assigned.id for option in options):
        options.append(
            FundOption(
                id=assigned.id,
                name=assigned.name,
                assigned=True,
                selectable=False,
                retired=True,
            )
        )
    return options
