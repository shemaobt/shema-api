from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.models.journey import JourneyResponse
from app.services.journey.get_visible_journey_ids import get_visible_journey_ids
from app.services.journey.list_journeys import list_journeys


async def list_journeys_for_user(db: AsyncSession, user: User) -> list[JourneyResponse]:
    """The catalog as this account is allowed to see it (OBT-507).

    Split from `list_journeys` to keep the scoping decision in one place,
    `get_visible_journey_ids`. A platform admin comes through here too and
    reaches `list_journeys` with `None`, which drops the filter — nothing else
    calls it.
    """
    return await list_journeys(db, journey_ids=await get_visible_journey_ids(db, user))
