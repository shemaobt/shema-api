"""Who writes an instance — reading it is not editing it (BE-25, OBT-534).

GATE-04 D2 (OBT-519, Daniel, 23/sep/2026): *"apenas quem iniciou a escrita consegue
preencher"*. Every member of the project reads the instance (``get_request``); **only
``started_by`` writes it, and so does the Admin** — nobody else. BE-19 (OBT-520) had left the
mesa and the Gestor able to write any draft, on GATE-02 D4 (27/aug/2026: the mesa may edit what
the team wrote). **The 23/sep decision revises that answer**, and it is Daniel's, not Karina's:
a draft somebody is typing into cannot also be typed into from the board, and the mesa's
correction of a submitted text is the revision's job, which stays open to her
(``require_reviser``).

**The Admin is the platform admin or whoever holds this app's ``admin`` role** — the Admin of
OBT-522, seeded in this app by ``scripts/seed_apps_roles.py``. Only the first reaches the
editing routes today: the ``admin`` role carries no capability of the frontend's table, so
``CanEditRequests`` refuses it before this module is asked. Recorded rather than widened here,
because the capability table is the frontend's (``capabilities.json``) and widening it is a
re-emission, not a line in this file.

The refusal is a **403 and not a 404**: the caller can already ``GET`` the instance, so hiding
its existence here would contradict the read one route over. A cancelled instance answers
**409** to every write, whoever asks: it was given up, and the way forward is a new start.
"""

from typing import NamedTuple, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, ConflictError
from app.db.models.auth import User
from app.db.models.resource_request import RRRequest
from app.services.resource_request._membership import granted_roles
from app.services.resource_request._scope import reach
from app.services.shema._scope import ADMIN_ROLE


async def is_admin(db: AsyncSession, user: User, app_key: str) -> bool:
    """The Admin of OBT-522: the platform admin, or this app's ``admin`` grant."""
    if user.is_platform_admin:
        return True
    return ADMIN_ROLE in await granted_roles(db, user.id, app_key)


class Edits(Protocol):
    """Whether *this caller* writes a given instance — a user's ``Editing`` or a link's."""

    def can_edit(self, request: RRRequest) -> bool: ...


class Editing(NamedTuple):
    """Whether a caller writes a given instance, answered from one read of their roles.

    A value and not a function per row, for the listing's sake: ``can_edit`` rides on every
    envelope, and asking the roles once per row would be the N+1 ``Reach`` was written to
    avoid.
    """

    user_id: str
    admin: bool

    def holds_the_pen(self, request: RRRequest) -> bool:
        return self.admin or request.started_by == self.user_id

    def can_edit(self, request: RRRequest) -> bool:
        """What the screen needs to know: an open draft this caller writes."""
        open_draft = request.submitted_at is None and request.cancelled_at is None
        return open_draft and self.holds_the_pen(request)


async def editing(db: AsyncSession, user: User, app_key: str) -> Editing:
    return Editing(user_id=user.id, admin=await is_admin(db, user, app_key))


async def require_editor(db: AsyncSession, request: RRRequest, user: User, app_key: str) -> None:
    """Refuse ``user`` unless they started ``request`` or are the Admin; refuse a cancelled one.

    Whether the draft was already submitted stays each caller's check, with its own sentence:
    what a frozen request refuses reads differently for a file than for a document.
    """
    if not (await editing(db, user, app_key)).holds_the_pen(request):
        raise AuthorizationError(
            "Only whoever started this request writes it; the rest of the team reads it."
        )
    if request.cancelled_at is not None:
        raise ConflictError("This request was cancelled; start a new one instead.")


async def require_reviser(db: AsyncSession, request: RRRequest, user: User, app_key: str) -> None:
    """Refuse ``user`` unless they started ``request`` or reach the whole board.

    Opening a revision is not typing into a draft: it reopens a frozen request the mesa asked
    to be revised, and the new draft's pen goes to whoever held the old one. The mesa and the
    Gestor keep that door — the one form GATE-02 D4 still has after the 23/sep revision.
    """
    if request.started_by == user.id:
        return
    if (await reach(db, user, app_key)).every:
        return
    raise AuthorizationError("Only whoever started this request, or the board, opens its revision.")
