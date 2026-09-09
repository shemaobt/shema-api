from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.resource_request import RRRequestFieldHistory
from app.services.resource_request.get_request import get_request


async def list_request_history(
    db: AsyncSession, request_id: str, user: User, app_key: str
) -> list[RRRequestFieldHistory]:
    """A request's field-by-field trail, oldest change first — for whoever reaches the request.

    **Who may read it, and why — the decision BE-15 owes in writing.** The trail of the
    solicitação is scoped exactly like the solicitação: the ``get_request`` call is the
    guard, so the owning team reads it, the mesa and the Gestor read it, and anyone else
    gets the same 404 the document itself answers. The team is *in* deliberately — GATE-02
    D4 lets the mesa edit what the team wrote, and this trail is how a team sees its own
    document's edits, which is part of owning it; the mesa and the Gestor are in because
    auditing who changed what is the thing D7 asked for. Nothing here needs a capability of
    its own: the trail carries only request fields, which every holder of ``edit_requests``
    may already read in their current values. The **avaliação's** trail is a different
    answer — it carries scores and a decision, content ``view_evaluation`` gates — and its
    read surface arrives with BE-06's evaluation endpoints, not here.

    Ordered by ``changed_at`` then ``field_key``: the writer stamps one instant per save,
    so saves order between themselves and a save's own rows order deterministically —
    within one save there is no truer order to claim.
    """
    await get_request(db, request_id, user, app_key)

    rows = await db.execute(
        select(RRRequestFieldHistory)
        .where(RRRequestFieldHistory.request_id == request_id)
        .order_by(RRRequestFieldHistory.changed_at, RRRequestFieldHistory.field_key)
    )
    return list(rows.scalars().all())
