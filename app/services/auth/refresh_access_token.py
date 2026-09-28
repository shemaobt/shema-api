from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AuthorizationError
from app.services.auth.get_user_by_id import get_user_by_id
from app.services.auth.read_live_refresh_token import read_live_refresh_token
from app.utils.jwt import create_token

settings = get_settings()


async def refresh_access_token(db: AsyncSession, refresh_token: str) -> str:

    token_record = await read_live_refresh_token(db, refresh_token)

    user = await get_user_by_id(db, token_record.user_id)
    if not user or not user.is_active:
        raise AuthorizationError("Inactive or missing user")

    return create_token(user.id, "access", settings.access_token_expire_minutes)
