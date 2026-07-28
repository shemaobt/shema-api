from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.sound_necklace import SnSession


@dataclass(frozen=True)
class LockState:
    """Who holds a session's lease right now, as the SPA needs to hear it."""

    held: bool
    user_id: str | None = None
    display_name: str | None = None
    expires_at: datetime | None = None


UNHELD = LockState(held=False)


def holder_name(display_name: str | None, email: str) -> str:
    """A name for the "sessão em uso por…" banner.

    display_name is nullable in the database but the SPA's LockHolder requires a
    string, so the email stands in rather than the screen reading "None".
    """
    return display_name or email


def as_utc(when: datetime) -> datetime:
    """Read a stored expiry back as an instant.

    Postgres hands back an aware datetime and SQLite a naive one, so without this the
    wire would carry an offset in production and none under test — and the SPA reads
    expires_at as an instant either way.
    """
    return when.replace(tzinfo=UTC) if when.tzinfo is None else when


async def get_lock_status(db: AsyncSession, session_id: str) -> LockState:
    """Report the live holder of a session's lease, if any.

    A lapsed lease reads as unheld: nothing sweeps expired rows, so expiry is decided
    on read rather than by a janitor.
    """
    row = (
        await db.execute(
            select(SnSession.locked_by, SnSession.lock_expires_at, User.display_name, User.email)
            .join(User, User.id == SnSession.locked_by)
            .where(SnSession.id == session_id, SnSession.lock_expires_at > datetime.now(UTC))
        )
    ).first()
    if row is None:
        return UNHELD
    locked_by, expires_at, display_name, email = row
    return LockState(True, locked_by, holder_name(display_name, email), as_utc(expires_at))
