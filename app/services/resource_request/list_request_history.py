from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.resource_request import RRRequestFieldHistory
from app.services.resource_request._names import display_names_of
from app.services.resource_request.get_request import get_request


class AuthoredChange(NamedTuple):
    """One trail row with the one answer the row cannot give: who ``changed_by`` names today.

    ``None`` for a row a link's holder wrote — there is no account to name — and for an
    account with no ``display_name``; never the e-mail (OBT-685).
    """

    row: RRRequestFieldHistory
    changed_by_name: str | None


async def list_request_history(
    db: AsyncSession, request_id: str, user: User, app_key: str
) -> list[AuthoredChange]:
    """A request's field-by-field trail, oldest change first — for whoever reaches the request.

    **Who may read it, and why — the decision BE-15 owes in writing.** The trail of the solicitação
    is scoped exactly like the solicitação: the ``get_request`` call is the guard, so the owning
    team reads it, the mesa and the Gestor read it, and anyone else gets the same 404 the document
    itself answers. The team is *in* deliberately — the Admin may edit what a member started
    (GATE-02 D4, narrowed by BE-25), and this trail is how a team sees its own document's edits,
    which is part of owning it; the mesa and the Gestor are in because auditing who changed what is
    the thing D7 asked for. Nothing here needs a capability of its own: the trail carries only
    request fields, which every holder of ``edit_requests`` may already read in their current
    values. The **avaliação's** trail is a different answer — it carries scores and a decision,
    content ``view_evaluation`` gates — and its read surface is ``list_evaluation_history``
    behind that capability (OBT-672), not here.

    Ordered by ``changed_at`` then ``field_key``: the writer stamps one instant per save,
    so saves order between themselves and a save's own rows order deterministically —
    within one save there is no truer order to claim.

    **The author's name is resolved here, from one statement, and is never stored** (OBT-685;
    Daniel, 05/nov/2026). The row keeps the id, because the trail is append-only and a name
    is not — a user renamed after the edit reads with the new name over the same row. What
    is resolved is the ``display_name`` and never the e-mail: the team reads this trail, and
    the address of whoever on the mesa or the Gestor corrected its document is not the
    team's to read. A link's holder has no account and answers ``None``, as does an account
    with no ``display_name`` — the screen says so rather than showing an id or inventing a
    name.
    """
    await get_request(db, request_id, user, app_key)

    rows = await db.execute(
        select(RRRequestFieldHistory)
        .where(RRRequestFieldHistory.request_id == request_id)
        .order_by(RRRequestFieldHistory.changed_at, RRRequestFieldHistory.field_key)
    )
    changes = list(rows.scalars().all())
    names = await display_names_of(
        db, (row.changed_by for row in changes if row.changed_by is not None)
    )
    return [
        AuthoredChange(row, names.get(row.changed_by) if row.changed_by is not None else None)
        for row in changes
    ]
