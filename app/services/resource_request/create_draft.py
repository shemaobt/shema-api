from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.resource_request import RRBudgetLine, RRRequest, RRRequestSections
from app.models.resource_request import RequestDraftIn
from app.services.resource_request._document import split


async def create_draft(db: AsyncSession, draft: RequestDraftIn, author_id: str) -> RRRequest:
    """Open a request on the server, owned by the session that opened it.

    ``author_id`` comes from the bearer token and never from the payload. GATE-02 D1 made
    that possible by answering that everyone has an account — the design's §5.2 named the
    cost of the other answer, an author with no stable identity, and it is the reason
    ``created_by`` is nullable in the schema and non-null in practice.

    ``stage`` is left to the column's own default, ``triagem``. A request that has not been
    submitted is not on the board yet, and giving it a stage here would be this service
    deciding something BE-08 owns.
    """
    parts = split(draft)

    request = RRRequest(**parts.spine, created_by=author_id)
    db.add(request)
    await db.flush()

    db.add(RRRequestSections(request_id=request.id, content=parts.sections))
    for line in parts.budget:
        db.add(RRBudgetLine(request_id=request.id, **line))

    await db.commit()
    await db.refresh(request)
    return request
