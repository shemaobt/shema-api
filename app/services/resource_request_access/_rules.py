"""Grant rules for invite acceptance, and the mesa/Gestor rule the Shemá Admin's surface imports.

The naming door that shared them left with the form's access screen (FE-56, OBT-549): roles
are granted in the PME now. What follows was written for both doors and still holds for the
one that stays.

``mesa`` and ``gestor`` exclude each other because they are the two privileged
seats and the client's model has a person on one side of the table at a time;
``equipe`` is the floor and accumulates beside either. The check runs at grant
time — both at naming and at invite acceptance — because acceptance can happen
long after the invite was written, against a user whose roles have changed.

**``admin`` and ``mesa`` exclude each other too, since OBT-568** (Daniel, 6/oct/2026, in the
issue's comments: an account cannot be Admin and mesa, as it cannot be Gestor and mesa). The
Admin holds the Gestor's capabilities in the form (``resource_request/capabilities.py``), so
an Admin on the mesa would be the mesa + Gestor union by another name. ``admin`` + ``gestor``
stays allowed — it is the shape the Admin's own account has. The ``admin`` grant writes both
apps, and the check runs per app: under ``shema`` there is no ``mesa`` role to collide with
and the rule is silent; under the form it refuses.

**Naming the ``admin`` role is the PME's concern now.** The form's naming and
invite-issuing doors refused an ``admin`` to anyone but an installation admin
(``assert_role_grantable``, OBT-523); both doors left with FE-56, and so did that
check. Invites are issued by the PME (``/api/shema/access``, OBT-543), behind the
Admin's own gate.

**The Shemá Admin's surface imports** ``assert_role_compatible`` — the one owner
of the rule that keeps mesa and Gestor apart, for both surfaces. OBT-549 retired the naming
door and left this file in place on purpose (option A, 30/sep): deleting it breaks the PME's
grants, and moving it into the Shemá module is a follow-up on Levi's surface.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.db.models.auth import UserAppRole
from app.services.authorization.get_role import get_role

#: Each role and the roles it cannot sit beside, symmetric by construction below.
MUTUALLY_EXCLUSIVE: dict[str, tuple[str, ...]] = {
    "mesa": ("gestor", "admin"),
    "gestor": ("mesa",),
    "admin": ("mesa",),
}


async def assert_role_compatible(
    db: AsyncSession, user_id: str, app_id: str, role_key: str
) -> None:
    """Refuse a grant whose exclusive counterpart the user already holds."""
    for counterpart in MUTUALLY_EXCLUSIVE.get(role_key, ()):
        other_role = await get_role(db, app_id, counterpart)
        if not other_role:
            continue

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
