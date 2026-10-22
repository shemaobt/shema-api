from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_cache import get_cached_roles, set_cached_roles
from app.db.models.auth import User
from app.services.authorization.list_roles import list_roles


async def roles_on(db: AsyncSession, user: User, app_key: str) -> list[tuple[str, str]]:
    """The user's roles on one app, off the cache every role gate shares."""
    roles = get_cached_roles(user.id, app_key)
    if roles is None:
        roles = await list_roles(db, user.id, app_key)
        set_cached_roles(user.id, app_key, roles)
    return roles
