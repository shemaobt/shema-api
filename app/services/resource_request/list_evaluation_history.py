from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.resource_request import RREvaluation, RREvaluationFieldHistory, RRSnapshot
from app.services.resource_request.get_request import get_request


async def list_evaluation_history(
    db: AsyncSession, request_id: str, user: User, app_key: str
) -> list[RREvaluationFieldHistory]:
    """The avaliação's field-by-field trail, oldest change first (OBT-672).

    **The route in front gates on ``view_evaluation``**, the capability the team does not
    hold: the trail carries scores, a decision and the mesa's comments, which is exactly
    the content that capability exists to keep from a team. ``get_request`` is still the
    scope — anyone who cannot reach the request gets the same 404 the request answers — so
    the gate says *may read an evaluation* and the scope says *this request*.

    **It answers for one request, and a revision is another request.** ``open_revision``
    mints a new ``rr_requests`` row whose ``revision_of_id`` points at the evaluated
    snapshot (BE-04), so the revision's evaluation — and its trail — hang off the new id,
    and the original keeps its own, frozen with the decision that asked for the revision.
    Reading both is reading two ids, which is what the console already does to show a
    revision beside what it revised. (The first cut of this docstring said the trail spanned
    every snapshot of the request; the review found that a request has one, and the join on
    ``RRSnapshot.request_id`` below is what makes that true rather than a promise.) A request
    nobody has evaluated has an empty trail, not a 404: *no changes yet* is an answer, and it
    is the one a screen can draw.

    Ordered by ``changed_at`` then ``field_key``, as the request's trail is: one save stamps
    one instant, so saves order between themselves and a save's rows order deterministically.
    """
    await get_request(db, request_id, user, app_key)

    rows = await db.execute(
        select(RREvaluationFieldHistory)
        .join(RREvaluation, RREvaluation.id == RREvaluationFieldHistory.evaluation_id)
        .join(RRSnapshot, RRSnapshot.id == RREvaluation.snapshot_id)
        .where(RRSnapshot.request_id == request_id)
        .order_by(RREvaluationFieldHistory.changed_at, RREvaluationFieldHistory.field_key)
    )
    return list(rows.scalars().all())
