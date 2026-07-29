from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AuthorizationError
from app.db.models.auth import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_current_user(
    db: AsyncSession = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> User:
    from app.services import auth_service

    return await auth_service.get_current_user_from_access_token(db, token)


async def require_platform_admin(
    user: User = Depends(get_current_user),
) -> User:
    if not user.is_platform_admin:
        raise AuthorizationError("Forbidden")
    return user


async def require_admin_or_manager(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> User:
    if user.is_platform_admin:
        return user

    from app.core.org_scope import get_managed_org_ids, get_managed_project_ids

    if await get_managed_org_ids(db, user.id) or await get_managed_project_ids(db, user.id):
        return user

    raise AuthorizationError("Forbidden")
