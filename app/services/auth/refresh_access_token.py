from datetime import UTC, datetime

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.db.models.auth import RefreshToken
from app.services.auth.get_user_by_id import get_user_by_id
from app.services.auth.hash_refresh_token import hash_refresh_token
from app.utils.jwt import create_token, decode_token
from app.utils.stored_time import as_utc

settings = get_settings()


async def refresh_access_token(db: AsyncSession, refresh_token: str) -> str:

    payload = decode_token(refresh_token)
    if payload.get("type") != "refresh":
        raise AuthenticationError("Invalid token type")

    token_hash = hash_refresh_token(refresh_token)
    stmt: Select[tuple[RefreshToken]] = select(RefreshToken).where(
        RefreshToken.token_hash == token_hash,
        RefreshToken.revoked_at.is_(None),
    )
    result = await db.execute(stmt)
    token_record = result.scalar_one_or_none()
    if not token_record:
        raise AuthenticationError("Refresh token revoked or missing")

    if as_utc(token_record.expires_at) < datetime.now(UTC):
        raise AuthenticationError("Refresh token expired")

    user = await get_user_by_id(db, payload["sub"])
    if not user or not user.is_active:
        raise AuthorizationError("Inactive or missing user")

    return create_token(user.id, "access", settings.access_token_expire_minutes)
