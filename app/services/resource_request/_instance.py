"""One open instance per project — GATE-04 D6 (OBT-519, Daniel, 23/sep/2026), BE-25 (OBT-534).

*Open* is a row neither submitted nor cancelled. Two things carry the rule and they are not
redundant: ``uq_rr_requests_one_open_per_project`` is the guarantee, and it is what holds when
two members press *Iniciar* in the same second; the question asked here first is what gives
the ordinary case a sentence instead of an integrity error. ``flush_the_instance`` turns the
index's refusal into the same 409, so the race and the ordinary case read alike on the wire.

A request with no project is outside the rule by construction — the board's door (FE-41) and
the link's (BE-26) until OBT-547 registers the project. **The rule counts open instances, and
OBT-508's *uma solicitação de tradução por projeto* counts submitted ones**: two rules, one line
each (``count_project_translations``), and neither reads the other.
"""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.db.models.resource_request import RRRequest

_ALREADY_OPEN = (
    "This project already has a request being filled in. Only one is open at a time: "
    "whoever started it submits or cancels it first."
)


async def refuse_a_second_open(db: AsyncSession, project_id: str | None) -> None:
    if project_id is None:
        return
    open_one = await db.execute(
        select(RRRequest.id)
        .where(
            RRRequest.shema_project_id == project_id,
            RRRequest.submitted_at.is_(None),
            RRRequest.cancelled_at.is_(None),
        )
        .limit(1)
    )
    if open_one.scalar_one_or_none() is not None:
        raise ConflictError(_ALREADY_OPEN)


async def flush_the_instance(db: AsyncSession) -> None:
    """Flush a new instance, answering the index's refusal as the rule's 409."""
    try:
        await db.flush()
    except IntegrityError as collided:
        await db.rollback()
        if "uq_rr_requests_one_open_per_project" in str(collided.orig) or "shema_project_id" in str(
            collided.orig
        ):
            raise ConflictError(_ALREADY_OPEN) from None
        raise
