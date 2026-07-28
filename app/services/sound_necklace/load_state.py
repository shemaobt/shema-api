from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.sound_necklace import SnSessionState


async def load_state(db: AsyncSession, session_id: str) -> tuple[str, int]:
    """The stored state document and its version, for a resume.

    Raises NotFoundError while the session has never been autosaved — there is
    nothing to resume from yet.
    """
    result = await db.execute(
        select(SnSessionState.state, SnSessionState.version).where(
            SnSessionState.session_id == session_id
        )
    )
    row = result.one_or_none()
    if row is None or row.state is None:
        raise NotFoundError("Session state not found")
    return row.state, row.version
