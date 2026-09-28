"""What accepting an invitation does with the regions it carries (OBT-543).

Called by ``resource_request_access.accept_invite`` before it grants the invite's role, and
inside its transaction. The regions become the account's scope, as a grant's do — **unless
the account already holds a regional role and a different scope.** An invite is written for
somebody with no account; by the time it is accepted an Admin may have granted that person
something directly, and a week-old link must not rewrite a newer decision. Then the answer
is 409, and the Admin grants the role directly. The same scope is accepted as a no-op.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.services.shema._scope import REGIONAL_ROLES, granted_roles
from app.services.shema.set_region_scope import held_regions, set_region_scope


async def apply_invited_scope(
    db: AsyncSession,
    user_id: str,
    region_keys: Sequence[str],
    *,
    app_key: str,
    invited_by: str | None,
) -> None:
    """Write ``region_keys`` as the account's scope, or refuse a change to an existing one."""
    held = await granted_roles(db, user_id, app_key)
    if held.intersection(REGIONAL_ROLES):
        current = {row.region_key.value for row in await held_regions(db, user_id)}
        if current != set(region_keys):
            raise ConflictError(
                "This account already has a region scope, and accepting this invitation "
                "would change it. The Admin grants the role directly instead."
            )
    await set_region_scope(db, user_id, region_keys, granted_by=invited_by, commit=False)
