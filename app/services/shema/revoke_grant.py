"""``POST /access/grants/revoke`` — the Admin takes a role back, with who and when.

Refusals first and one commit, for ``grant_role``'s reason. The revocation goes through the
platform's ``revoke_role``, which records ``revoked_by`` beside ``revoked_at``, in every app
the role lives in — both for ``admin`` — and closes any invite still pending for the same
e-mail, app and role, so a week-old link cannot hand back what was just taken.

**Revoking the last regional role clears the account's regions.** A row counts only under a
regional role (``_scope.py``), so the rows left behind reach nothing today — but the next
regional grant through a door that states no region would bring them back: an approved
access request hands out ``resourceCircle`` with no region at all. Clearing them here is what
keeps an old scope from coming back by accident, and the trail records it.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_cache import invalidate_roles
from app.core.exceptions import RoleError
from app.db.models.auth import User
from app.models.shema_grant import AccountGrants, RoleRevokeRequest
from app.services.authorization.list_roles import list_roles
from app.services.authorization.revoke_role import revoke_role
from app.services.resource_request_access.invite_store import recall_pending_invites
from app.services.shema._grant_rules import (
    GrantApps,
    apps_for,
    lock_account,
    require_admin_in,
    require_grantable,
)
from app.services.shema._scope import REGIONAL_ROLES
from app.services.shema.find_account import account_grants
from app.services.shema.set_region_scope import set_region_scope


async def revoke_grant(
    db: AsyncSession, apps: GrantApps, *, payload: RoleRevokeRequest, actor: User
) -> AccountGrants:
    """Revoke ``payload``'s role from its account, and answer the account as it now stands."""
    role_key = payload.role_key
    require_grantable(apps, payload.app_key, role_key)
    if payload.user_id == actor.id:
        raise RoleError("You cannot revoke your own role.")

    account = await lock_account(db, payload.user_id)
    touched = apps_for(apps, payload.app_key, role_key)
    await require_admin_in(db, actor, touched)
    held = set(await list_roles(db, account.id))
    holding = [app_key for app_key in touched if (app_key, role_key) in held]
    if not holding:
        raise RoleError("Active assignment not found")

    for app_key in holding:
        await revoke_role(db, actor, account.id, app_key, role_key, commit=False)
    for app_key in touched:
        await recall_pending_invites(
            db, actor, email=account.email, app_key=app_key, role_key=role_key
        )
    if role_key in REGIONAL_ROLES:
        remaining = {role for app, role in held if app == apps.shema} - {role_key}
        if not remaining.intersection(REGIONAL_ROLES):
            await set_region_scope(db, account.id, [], granted_by=actor.id, commit=False)
    await db.commit()
    invalidate_roles(account.id)
    return await account_grants(db, apps, account)
