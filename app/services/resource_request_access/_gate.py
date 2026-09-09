"""The asymmetric gate: who may concede and who may revoke.

Kept apart from the shared ``assert_can_manage_roles`` on purpose — see the
package docstring for the full argument. Both checks raise ``AuthorizationError``
(403), not ``RoleError`` (400): being the wrong person is not a malformed
request.

**The concession reads the capability table, and does not name a role.** It used
to ask ``has_role(..., "gestor")``, which was the same rule written twice: once
in ``ROLE_CAPABILITIES``, mirrored from the frontend, and once as a literal here.
Two statements of one fact drift, and this pair did — the bench found on
4/set/2026 that the vendored emission held nine capabilities while the frontend
emitted ten, ``grant_access`` being the missing one, with both repositories' CI
green the whole time because each compares itself against itself. The literal is
gone: whoever the table says holds ``grant_access`` concedes, and moving that
row moves this gate with it.

What did **not** change is the asymmetry the client asked for (28/aug/2026):
*"Admin e Gestor"* concede and *"Admin"* revokes. The Gestor holds
``grant_access``; nobody holds a revoke capability, because revoking is not a
role's power in this app at all — it is the platform Admin's, which is a fact of
the person and not a row in any table.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError
from app.db.models.auth import User
from app.services.resource_request.holds_capability import holds_capability

GRANT_CAPABILITY = "grant_access"


async def assert_can_grant(db: AsyncSession, actor: User, app_key: str) -> None:
    """Admin (platform) and whoever holds ``grant_access`` concede."""
    if actor.is_platform_admin:
        return
    if await holds_capability(db, actor.id, app_key, GRANT_CAPABILITY):
        return
    raise AuthorizationError("Only an Admin or a Gestor can grant access to this application.")


def assert_can_revoke(actor: User) -> None:
    """Only Admin (platform) revokes — the Gestor deliberately cannot."""
    if actor.is_platform_admin:
        return
    raise AuthorizationError("Only an Admin can revoke access to this application.")
