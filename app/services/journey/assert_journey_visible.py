from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError
from app.db.models.auth import User
from app.services.journey.get_visible_journey_ids import get_visible_journey_ids


async def assert_journey_visible(db: AsyncSession, user: User, journey_id: str) -> None:
    """Refuse a journey this account may not read.

    Without it the scoped listing would be cosmetic: a manager handed one id
    could still open any journey by asking for it directly. Refused with 403
    rather than 404 to match `assert_project_access`, which the same Console
    screens already surface.
    """
    visible = await get_visible_journey_ids(db, user)
    if visible is None or journey_id in visible:
        return
    raise AuthorizationError("You do not have access to this journey")
