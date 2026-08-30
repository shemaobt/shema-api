"""Grant rules shared by the two doors (naming and invite-accept).

``mesa`` and ``gestor`` exclude each other because they are the two privileged
seats and the client's model has a person on one side of the table at a time;
``equipe`` is the floor and accumulates beside either. The check runs at grant
time — both at naming and at invite acceptance — because acceptance can happen
long after the invite was written, against a user whose roles have changed.

The timestamp helper exists because ``DateTime(timezone=True)`` reads back
naive on SQLite and aware on Postgres; a naive value here is by construction
UTC.
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.db.models.auth import UserAppRole
from app.services.authorization.get_role import get_role

MUTUALLY_EXCLUSIVE: dict[str, str] = {"mesa": "gestor", "gestor": "mesa"}


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


def as_aware_utc(value: datetime) -> datetime:
    """Read a stored moment back onto the UTC clock it was written on."""
    return value if value.tzinfo else value.replace(tzinfo=UTC)
