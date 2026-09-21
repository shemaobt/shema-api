from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.models.journey import JourneyResponse
from app.services.journey.get_visible_journey_ids import get_visible_journey_ids
from app.services.journey.list_journeys import list_journeys


async def list_journeys_for_user(db: AsyncSession, user: User) -> list[JourneyResponse]:
    """The catalog as this account is allowed to see it (OBT-507).

    Kept apart from `list_journeys`, which still answers "every journey" for the
    callers that legitimately want that (a platform admin, and the counts an
    admin screen shows); the scoping decision lives with
    `get_visible_journey_ids` alone.
    """
    return await list_journeys(db, journey_ids=await get_visible_journey_ids(db, user))
