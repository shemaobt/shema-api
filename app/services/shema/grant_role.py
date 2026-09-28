"""``POST /access/grants`` — the Admin grants a role, with its regions when it is regional.

**Every refusal happens before the first write.** The vocabulary, the regions, the
self-grant, the account, the Admin's own standing in every app the grant writes, that the
roles exist, and the exclusion between mesa and Gestor are all answered first; only then are
the rows written, and they are written in one commit. A refusal that came after a flush would leave
half a grant in a session nobody rolls back until it closes — and in the suite, where one
session serves every request, the next request would commit it.

What is written, in that one transaction: the role in each app it lives in (``admin`` in
both), through the platform's ``assign_role``; the close of any invite still pending for the
same e-mail, app and role, which the grant supersedes; and, for a regional role, the account's
whole region scope through ``set_region_scope``, which leaves its trail. Re-granting a role
the account holds writes no role row and restates the regions — that is how they are edited.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_cache import invalidate_roles
from app.core.exceptions import RoleError
from app.db.models.auth import User
from app.models.shema_grant import AccountGrants, RoleGrantRequest
from app.services.authorization.assign_role import assign_role
from app.services.authorization.get_app_by_key import get_app_by_key
from app.services.authorization.get_role import get_role
from app.services.resource_request_access._rules import assert_role_compatible
from app.services.resource_request_access.invite_store import recall_pending_invites
from app.services.shema._grant_rules import (
    GrantApps,
    apps_for,
    lock_account,
    require_admin_in,
    require_grantable,
    require_regions,
)
from app.services.shema.find_account import account_grants
from app.services.shema.set_region_scope import set_region_scope


async def grant_role(
    db: AsyncSession, apps: GrantApps, *, payload: RoleGrantRequest, actor: User
) -> AccountGrants:
    """Grant ``payload``'s role to its account, and answer the account as it now stands."""
    role_key = payload.role_key
    require_grantable(apps, payload.app_key, role_key)
    regions = require_regions(role_key, (key.value for key in payload.region_keys))
    if payload.user_id == actor.id:
        raise RoleError("You cannot grant a role to yourself.")

    account = await lock_account(db, payload.user_id)
    touched = apps_for(apps, payload.app_key, role_key)
    await require_admin_in(db, actor, touched)
    for app_key in touched:
        app = await get_app_by_key(db, app_key)
        if app is None:
            raise RoleError("App not found")
        if await get_role(db, app.id, role_key) is None:
            raise RoleError("Role not found")
        await assert_role_compatible(db, account.id, app.id, role_key)

    for app_key in touched:
        await assign_role(db, actor, account.id, app_key, role_key, commit=False)
        await recall_pending_invites(
            db, actor, email=account.email, app_key=app_key, role_key=role_key
        )
    if regions:
        await set_region_scope(db, account.id, regions, granted_by=actor.id, commit=False)
    await db.commit()
    invalidate_roles(account.id)
    return await account_grants(db, apps, account)
