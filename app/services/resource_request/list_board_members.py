from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.services import authorization_service
from app.services.resource_request.capabilities import CAPABILITY_ROLES

#: Who sits on the mesa, read off the capability map rather than a role literal — the
#: ``BOARD_CAPABILITY`` reasoning in ``_notices.py``. ``edit_evaluation`` is the mesa's
#: alone: it scores and decides, which is what being on the mesa means, and the Gestor —
#: who *"só não aprova"* (GATE-02 D3) — is not in the room as a member.
MEMBER_CAPABILITY = "edit_evaluation"


async def list_board_members(db: AsyncSession, app_key: str) -> list[User]:
    """The mesa's members, to mark who was present when a decision is taken (FE-50, OBT-518).

    Karina, via Daniel, 1/out/2026: each member has *"conta própria"*, so the member list is
    whoever holds the mesa's role in this app — an account granted in the PME — and never a
    list of names kept here. Adding a member is granting the role; nothing in this module
    changes. Active accounts only, ordered by e-mail: ``list_role_holders``' own rules.
    """
    return await authorization_service.list_role_holders(
        db, app_key, CAPABILITY_ROLES[MEMBER_CAPABILITY]
    )
