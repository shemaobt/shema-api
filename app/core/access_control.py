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

    async def _check(
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        if user.is_platform_admin:
            return user
        ok = await authorization_service.has_role(db, user.id, app_key, role_key)
        if not ok:
            raise AuthorizationError(f"Role '{role_key}' is required for this action.")
        return user

    return Depends(_check)
