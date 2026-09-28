"""What the Admin's surface grants, and how — the one owner of its rules (OBT-543).

The surface (``docs/shema.md``, *The Admin grants*) is where OBT-522's Admin concedes and
revokes the roles of the two applications the PME serves. Every rule it applies that is a
question of *what* rather than *who* is written here, once, and built from
``_scope.py``'s constants rather than retyped:

- **The vocabulary is the PME's own.** From ``shema``, the four personas and ``admin``
  (``SHEMA_APP_ROLES``); from the form, ``admin`` and the two seats the PME's door counts
  (``FORM_DOOR_ROLES``). ``equipe`` is refused by name — it is a project membership since
  OBT-524, not a role this surface writes — and so is anything else, ``lider`` included,
  who has no account since 22/set.
- **``admin`` is one role for two apps.** Granting or revoking it under either app key
  writes the row in both, which is what OBT-523 left to this issue.
- **A regional role is granted with its regions, and no other role touches them.** The scope
  table is per account and ``set_region_scope`` replaces it whole, so a region list passed
  with ``admin`` would silently rewrite a coordinator's reach.

Who may act is ``require_admin_in``: the platform's own predicate, read fresh.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AuthorizationError,
    RoleError,
    UnknownReferenceError,
    UnprocessableValueError,
)
from app.db.models.auth import User
from app.services.authorization.assert_can_manage_roles import assert_can_manage_roles
from app.services.shema._scope import (
    ADMIN_ROLE,
    EQUIPE_ROLE,
    FORM_DOOR_ROLES,
    REGIONAL_ROLES,
    SHEMA_APP_ROLES,
)


class GrantApps(NamedTuple):
    """The two applications whose roles the surface grants, by key.

    The keys are named in ``app/api/shema/_deps.py`` and handed down, which is where the
    module keeps every app key.
    """

    shema: str
    form: str


def grantable_roles(apps: GrantApps) -> dict[str, tuple[str, ...]]:
    """Every role the surface writes, per app, in the session's precedence order."""
    return {apps.shema: SHEMA_APP_ROLES, apps.form: (ADMIN_ROLE, *FORM_DOOR_ROLES)}


def require_grantable(apps: GrantApps, app_key: str, role_key: str) -> None:
    """Refuse a role the surface does not write, with the reason the Admin can act on."""
    if role_key in grantable_roles(apps).get(app_key, ()):
        return
    if role_key == EQUIPE_ROLE:
        raise UnprocessableValueError(
            f"'{EQUIPE_ROLE}' is a project membership, added on the project, not a role "
            "granted here."
        )
    raise UnprocessableValueError(f"'{role_key}' is not a role granted here for '{app_key}'.")


def apps_for(apps: GrantApps, app_key: str, role_key: str) -> tuple[str, ...]:
    """The apps one grant of ``role_key`` writes: both for ``admin``, its own for the rest."""
    if role_key == ADMIN_ROLE:
        return (apps.shema, apps.form)
    return (app_key,)


def require_regions(role_key: str, region_keys: Iterable[str]) -> tuple[str, ...]:
    """The regions a grant writes — never empty for a regional role, always empty otherwise.

    An empty list and no list are the same answer: for a regional role both are refused,
    because a regional role with no region reaches nothing (``_scope.py``); for any other
    role both mean *leave the regions alone*.
    """
    keys = tuple(sorted(set(region_keys)))
    if role_key in REGIONAL_ROLES:
        if not keys:
            raise UnprocessableValueError(
                f"'{role_key}' is a regional role: grant it with at least one region."
            )
        return keys
    if keys:
        raise UnprocessableValueError(
            f"Regions go with a regional role only; '{role_key}' is not one."
        )
    return ()


def refuse_admin_by_link(role_key: str) -> None:
    """The Admin is granted to an account that exists, never through a link.

    A link can be forwarded, and signing up does not prove the e-mail is the person's, so
    the one role that grants every other role is not one a link may carry.
    """
    if role_key == ADMIN_ROLE:
        raise UnprocessableValueError(
            "The admin role is granted to an existing account, never through a link."
        )


async def require_admin_in(db: AsyncSession, actor: User, app_keys: Sequence[str]) -> None:
    """Refuse an actor who does not hold the Admin role in every app the act writes.

    **Read fresh**, not through the guard's cache: ``AdminUser`` answers from a list up to
    thirty seconds old in each process, and a write is where an Admin revoked a moment ago
    must already be refused. It is the platform's own predicate
    (``assert_can_manage_roles``), answered as a 403 rather than its 400, because being the
    wrong person is not a malformed request. The one account it refuses that the route let
    through is an Admin holding the role in one app only, and the sentence says so.
    """
    for app_key in dict.fromkeys(app_keys):
        try:
            await assert_can_manage_roles(db, actor, app_key)
        except RoleError as refused:
            raise AuthorizationError(
                f"The admin role is not held in '{app_key}'. Granting the Admin writes it in "
                "both apps; an installation admin can grant it again to repair this account."
            ) from refused


async def lock_account(db: AsyncSession, user_id: str) -> User:
    """The account a grant or a revocation writes to, locked for the rest of the transaction.

    ``SELECT … FOR UPDATE`` serializes two acts on one account on PostgreSQL, which is what
    keeps ``grant_app_role``'s check-then-insert from leaving two live rows and two
    concurrent requests from seating one person as both mesa and Gestor. SQLite — the suite —
    ignores the clause, so that half is argued here rather than proved there. An unknown id
    is a 422, the form's answer for the same request.
    """
    stmt = select(User).where(User.id == user_id).with_for_update()
    account = (await db.execute(stmt)).scalar_one_or_none()
    if account is None:
        raise UnknownReferenceError("Target user not found.")
    return account
