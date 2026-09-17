from typing import Any

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_cache import get_cached_roles, set_cached_roles
from app.core.auth_middleware import get_current_user
from app.core.database import get_db
from app.core.exceptions import AuthorizationError
from app.db.models.auth import User
from app.services import authorization_service


def require_app_access(app_key: str) -> Any:

    async def _check(
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        if user.is_platform_admin:
            return user
        roles = get_cached_roles(user.id, app_key)
        if roles is None:
            roles = await authorization_service.list_roles(db, user.id, app_key)
            set_cached_roles(user.id, app_key, roles)
        if not roles:
            raise AuthorizationError(
                f"You don't have access to the '{app_key}' application. "
                "Please contact support to request access."
            )
        return user

    return Depends(_check)


def require_role(app_key: str, role_key: str) -> Any:
    """Gate on one named role, off the same cached read ``require_app_access`` uses.

    It asked ``has_role`` until ENG-438, which is three round trips in a row — the app,
    then the role, then the grant — paid on **every** request, while the looser gate beside
    it paid one per cache window. That looser gate already reads the list this needs:
    ``list_roles`` answers ``(app_key, role_key)`` pairs, so holding a named role is a
    membership test on something already in hand.

    The two gates now share one cache entry per user and app, which is what makes them
    agree. A revocation still closes the door on the next request — ``grant_app_role`` and
    ``revoke_role`` both call ``invalidate_roles``. A grant or a revocation written
    **outside this process**, in the Tripod Console or by hand, is not seen until the entry
    ages out. That was already true of ``require_app_access`` and is the installation's
    standing trade; it is written down here because this is the tighter of the two gates
    and somebody will need to know which way it fails. How long it stays that way is
    ``auth_cache.AUTH_CACHE_TTL_SECONDS``, cut from five minutes to thirty seconds by
    ENG-551 — read that module's docstring before changing it.
    """

    async def _check(
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        if user.is_platform_admin:
            return user
        roles = get_cached_roles(user.id, app_key)
        if roles is None:
            roles = await authorization_service.list_roles(db, user.id, app_key)
            set_cached_roles(user.id, app_key, roles)
        if (app_key, role_key) not in roles:
            raise AuthorizationError(f"Role '{role_key}' is required for this action.")
        return user

    return Depends(_check)
