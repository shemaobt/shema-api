"""The asymmetric gate: who may concede and who may revoke.

Kept apart from the shared ``assert_can_manage_roles`` on purpose — see the
package docstring for the full argument. Both checks raise ``AuthorizationError``
(403), not ``RoleError`` (400): being the wrong person is not a malformed
request.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError
from app.db.models.auth import User
from app.services.authorization.has_role import has_role

GESTOR_ROLE_KEY = "gestor"


async def assert_can_grant(db: AsyncSession, actor: User, app_key: str) -> None:
    """Admin (platform) and Gestor concede — anyone else is refused."""
    if actor.is_platform_admin:
        return
    if await has_role(db, actor.id, app_key, GESTOR_ROLE_KEY):
        return
    raise AuthorizationError("Only an Admin or a Gestor can grant access to this application.")


def assert_can_revoke(actor: User) -> None:
    """Only Admin (platform) revokes — the Gestor deliberately cannot."""
    if actor.is_platform_admin:
        return
    raise AuthorizationError("Only an Admin can revoke access to this application.")
