from datetime import UTC, datetime

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError
from app.db.models.auth import RefreshToken
from app.services.auth.hash_refresh_token import hash_refresh_token
from app.utils.jwt import decode_token
from app.utils.stored_time import as_utc


async def read_live_refresh_token(db: AsyncSession, refresh_token: str) -> RefreshToken:
    """The stored row behind a refresh token that can still be used, or a refusal.

    *Live* is three things at once: a signed refresh token, a row for it that nobody revoked,
    and a row whose clock has not run out. A logout revokes one row and a password reset
    revokes them all, so this is the one place a session that ended is told apart from one
    that is only signed.

    Two callers, which is why it is its own function: ``/refresh``, which renews the access
    token of a live session, and the handoff (BE-21), which may only carry a live session into
    another app. Every refusal is an ``AuthenticationError`` — the 401 a client answers by
    signing in again.
    """
    payload = decode_token(refresh_token)
    if payload.get("type") != "refresh":
        raise AuthenticationError("Invalid token type")

    stmt: Select[tuple[RefreshToken]] = select(RefreshToken).where(
        RefreshToken.token_hash == hash_refresh_token(refresh_token),
        RefreshToken.revoked_at.is_(None),
    )
    token_record = (await db.execute(stmt)).scalar_one_or_none()
    if not token_record:
        raise AuthenticationError("Refresh token revoked or missing")

    if as_utc(token_record.expires_at) < datetime.now(UTC):
        raise AuthenticationError("Refresh token expired")

    return token_record
