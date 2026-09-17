import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.auth import App, PasswordResetToken
from app.services.auth.get_user_by_email import get_user_by_email
from app.services.auth.hash_refresh_token import hash_refresh_token
from app.services.common.email import send_password_reset_email


async def request_password_reset(db: AsyncSession, email: str, app_key: str) -> None:
    """Create a password reset token and send the reset email.

    Always returns without error regardless of whether the email exists
    (prevents email enumeration). The token is committed before the e-mail
    leaves, and sending is best-effort (``send_email`` never raises), so a
    provider outage cannot roll back the domain write.
    """
    user = await get_user_by_email(db, email)
    if not user:
        return

    await db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        )
        .values(used_at=datetime.now(UTC))
    )

    raw_token = secrets.token_hex(32)
    token_hash = hash_refresh_token(raw_token)

    settings = get_settings()
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.password_reset_token_expire_minutes)

    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
    )
    await db.flush()

    result = await db.execute(select(App).where(App.app_key == app_key))
    app = result.scalar_one_or_none()
    base_url = app.app_url.rstrip("/") if app and app.app_url else "http://localhost:5173"
    app_name = app.name if app else app_key

    reset_url = f"{base_url}/reset-password?token={raw_token}"

    await db.commit()

    await send_password_reset_email(
        to_email=user.email,
        display_name=user.display_name,
        reset_url=reset_url,
        app_name=app_name,
    )
