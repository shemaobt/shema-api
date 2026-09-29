"""Who writes a request the caller reaches — reading it is not editing it (BE-19, OBT-520).

BE-19 opened the **read** of a request to every live member of its project, drafts included
(GATE-04 D2, ``get_request``). Three writes — ``update_draft``, ``store_attachment`` and
``open_revision`` — had ``get_request`` as their only check, so that read became a write: a
teammate could rewrite a draft somebody else started, with the field trail recording it in the
teammate's name, swap its budget file, or open the revision of a request that was not theirs.
OBT-520 says the draft is *só leitura para quem não o iniciou*, and who edits a project's
instance is OBT-534's to decide, never the scope's.

**Until OBT-534, the author writes, and so does whoever reaches the whole board** — the mesa,
the Gestor and the platform admin (``_scope.reach``'s ``every``), because GATE-02 D4 lets the
mesa edit what the team wrote and nothing has retired that yet. Everyone else the scope lets in
reads. The refusal is a **403 and not a 404**: the caller can already ``GET`` the request, so
hiding its existence here would contradict the read one route over.

``submit_request`` keeps its own, narrower rule — only the author signs, the platform admin
included — because submitting is the electronic acceptance in ``created_by``'s name, which no
reach transfers.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError
from app.db.models.auth import User
from app.db.models.resource_request import RRRequest
from app.services.resource_request._scope import reach


async def require_editor(db: AsyncSession, request: RRRequest, user: User, app_key: str) -> None:
    """Refuse ``user`` unless they started ``request`` or reach the whole board."""
    if request.created_by == user.id:
        return
    if (await reach(db, user, app_key)).every:
        return
    raise AuthorizationError(
        "Only whoever started this request edits it; you can read it as a member of its project."
    )
