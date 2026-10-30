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

    **It follows the request, not one snapshot**: a revision is a new snapshot with its own
    evaluation, and the question D7 asks — *"quem subiu uma nota de 2 para 5"* — is about
    the request's whole life. A request nobody has evaluated has an empty trail, not a 404:
    *no changes yet* is an answer, and it is the one a screen can draw.

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
