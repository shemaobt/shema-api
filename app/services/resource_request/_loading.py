"""Reading a request's three tables at once, because nothing useful reads one of them.

The spine, its section document and its budget lines are one aggregate that happens to be
stored in three places, for the reasons §4.2 gives — the spine is queried and the sections
are read whole. Every caller that wants content wants all three, so the load is written once
here rather than three times with three chances to forget the ``order_by``.
"""

from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.resource_request import RRBudgetLine, RRRequest, RRRequestSections


class Loaded(NamedTuple):
    request: RRRequest
    sections: RRRequestSections | None
    budget: list[RRBudgetLine]


async def load(db: AsyncSession, request_id: str) -> Loaded | None:
    """The three rows, or ``None`` when the spine is not there.

    ``None`` rather than raising, because who may know that a request does not exist is the
    caller's question and not this function's — the scoped readers turn both *missing* and
    *out of scope* into the same 404 on purpose.
    """
    request = (
        await db.execute(select(RRRequest).where(RRRequest.id == request_id))
    ).scalar_one_or_none()
    if request is None:
        return None

    sections = (
        await db.execute(
            select(RRRequestSections).where(RRRequestSections.request_id == request_id)
        )
    ).scalar_one_or_none()

    budget = list(
        (
            await db.execute(
                select(RRBudgetLine)
                .where(RRBudgetLine.request_id == request_id)
                .order_by(RRBudgetLine.category_key)
            )
        )
        .scalars()
        .all()
    )

    return Loaded(request=request, sections=sections, budget=budget)
