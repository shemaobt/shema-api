"""``GET /access/people`` — one account by exact e-mail, as the Admin's screen shows it.

An exact match and not a search: the form's screen matched a substring and would name the
first account that looked like what was typed (FE-30's own note). The answer is the account's
roles in the two apps the surface writes, its stored regions and what they reach, and — since
OBT-679 — the projects it is a live member of; the same shape is what a grant and a revocation
answer, so the screen redraws from one reply.

**The projects are built for the caller's reader**, like the Admin's list of pending projects
(``list_pending_projects.py``): a project is named by its language, and a sensitive project's
name can name the place, so each one leaves through
:class:`~app.models.shema_privacy.LeavingShape` with ``Readership.reader_of`` its region. The
Admin reads as the coordination everywhere (``_scope.COORDINATION_EVERYWHERE``), so it reads
every name as it is; nothing here decides that. *Live* is ``_scope.member_projects``'s — a stay
that ended, somebody else's membership and a project nobody confirmed are absent.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.auth import User
from app.models.shema_grant import AccountGrants, AccountProject, AppRoles, RegionGrant
from app.services.auth.get_user_by_email import get_user_by_email
from app.services.authorization.list_roles import list_roles
from app.services.shema._grant_rules import GrantApps, grantable_roles
from app.services.shema._scope import (
    Readership,
    member_projects,
    roles_from,
    scope_from_roles,
)
from app.services.shema.set_region_scope import held_regions
from app.utils.shema_facets import collation_key


async def find_account(
    db: AsyncSession, apps: GrantApps, *, email: str, readership: Readership
) -> AccountGrants:
    """The account whose e-mail is exactly ``email``, case aside — or ``NotFoundError``."""
    account = await get_user_by_email(db, email.strip())
    if account is None:
        raise NotFoundError("No account with this e-mail.")
    return await account_grants(db, apps, account, readership=readership)


async def account_grants(
    db: AsyncSession, apps: GrantApps, account: User, *, readership: Readership
) -> AccountGrants:
    """What ``account`` holds, among the roles the surface writes, and how far it reaches.

    One read of every live grant, filtered per app, in the session's precedence order;
    ``regionScope`` is ``_scope.scope_from_roles``' answer rather than a second spelling of
    the rule that a row counts only under a regional role.
    """
    pairs = await list_roles(db, account.id)
    held = {
        app_key: frozenset(role for app, role in pairs if app == app_key and role in allowed)
        for app_key, allowed in grantable_roles(apps).items()
    }
    shema_roles = {role for app, role in pairs if app == apps.shema}
    scope = await scope_from_roles(db, account, shema_roles)
    return AccountGrants(
        userId=account.id,
        email=account.email,
        displayName=account.display_name,
        isActive=account.is_active,
        apps=[
            AppRoles(appKey=app_key, roles=list(roles_from(roles)))
            for app_key, roles in held.items()
        ],
        regions=[
            RegionGrant(
                regionKey=row.region_key.value,
                grantedBy=row.granted_by,
                grantedAt=row.granted_at,
            )
            for row in await held_regions(db, account.id)
        ],
        regionScope=scope.wire,
        projects=await account_projects(db, account, readership),
    )


async def account_projects(
    db: AsyncSession, account: User, readership: Readership
) -> list[AccountProject]:
    """The projects ``account`` is a live member of, each named as ``readership`` reads it.

    One read, then ordered by the name as built and the id, so the list reads the same between
    calls and never orders by a name the reader was not handed (OBT-563). ``collation_key`` and
    not ``reading_key``: the readers of this surface — the Admin and an installation admin —
    read every name as it is, so there is no region key the console would print in words.
    """
    projects = (await db.execute(member_projects(account.id))).scalars()
    built = [
        AccountProject.read_by(project, readership.reader_of(project.region_key))
        for project in projects
    ]
    return sorted(built, key=lambda ref: (collation_key(ref.language_name), ref.id))
