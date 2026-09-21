from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError
from app.db.models.auth import User
from app.services.user.get_user_by_id import get_user_by_id


async def update_user(
    db: AsyncSession,
    user_id: str,
    acting_user: User,
    is_active: bool | None = None,
    is_platform_admin: bool | None = None,
    avatar_url: str | None = None,
    display_name: str | None = None,
    locale: str | None = None,
) -> User:
    user = await get_user_by_id(db, user_id)
    if user.id == acting_user.id and (is_platform_admin is not None or is_active is not None):
        raise AuthorizationError(
            "Platform admins cannot change their own role or deactivate themselves"
        )
    if display_name is not None:
        user.display_name = display_name
    if is_active is not None:
        user.is_active = is_active
    if is_platform_admin is not None:
        user.is_platform_admin = is_platform_admin
    if avatar_url is not None:
        user.avatar_url = avatar_url if avatar_url else None
    if locale is not None:
        user.locale = locale
    await db.commit()
    await db.refresh(user)
    return user
