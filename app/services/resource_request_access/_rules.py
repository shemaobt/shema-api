"""Grant rules shared by the two doors (naming and invite-accept).

``mesa`` and ``gestor`` exclude each other because they are the two privileged
seats and the client's model has a person on one side of the table at a time;
``equipe`` is the floor and accumulates beside either. The check runs at grant
time — both at naming and at invite acceptance — because acceptance can happen
long after the invite was written, against a user whose roles have changed.

**The ``admin`` role is named only by an installation admin** (OBT-523). The form
seeds ``admin`` since ``20260927_shema08`` — OBT-522's Admin, one role for both
apps — and both doors here grant any role the app has, while the Gestor holds
``grant_access``. Left open, a Gestor could name an Admin, and that Admin passes
``assert_can_manage_roles`` and revokes through ``/api/roles``: the opposite of
*só o Admin revoga* and of *o Gestor não administra papéis*. The concession of
the Admin lives in the PME since OBT-543, and through these doors only
``is_platform_admin`` names one. The key is spelled here, as
``assert_can_manage_roles`` spells it, rather than imported from the Shemá module
this package is composed into.

**The Shemá Admin's surface imports** ``assert_role_compatible`` — the one owner
of the rule that keeps mesa and Gestor apart, for both surfaces. When OBT-549 retires these doors,
move it with ``accept_invite``; deleting it with them breaks the PME's grants.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, ConflictError
from app.db.models.auth import User, UserAppRole
from app.services.authorization.get_role import get_role

MUTUALLY_EXCLUSIVE: dict[str, str] = {"mesa": "gestor", "gestor": "mesa"}

#: The role only an installation admin names through these doors.
ADMIN_ROLE = "admin"


def assert_role_grantable(actor: User, role_key: str) -> None:
    """Refuse naming or inviting the ``admin`` role to anyone but an installation admin."""
    if role_key == ADMIN_ROLE and not actor.is_platform_admin:
        raise AuthorizationError("Only an Admin can grant the Admin role.")


async def assert_role_compatible(
    db: AsyncSession, user_id: str, app_id: str, role_key: str
) -> None:
    """Refuse a grant whose exclusive counterpart the user already holds."""
    counterpart = MUTUALLY_EXCLUSIVE.get(role_key)
    if not counterpart:
        return

    other_role = await get_role(db, app_id, counterpart)
    if not other_role:
        return

    stmt = select(UserAppRole.id).where(
        UserAppRole.user_id == user_id,
        UserAppRole.app_id == app_id,
        UserAppRole.role_id == other_role.id,
        UserAppRole.revoked_at.is_(None),
    )
    held = (await db.execute(stmt)).scalar_one_or_none()
    if held:
        raise ConflictError(
            f"'{role_key}' and '{counterpart}' are mutually exclusive: "
            f"revoke '{counterpart}' before granting '{role_key}'."
        )
