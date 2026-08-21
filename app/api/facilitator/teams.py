"""The Desk's entry screen and the panel behind it, both addressed by team.

Split from the device routes rather than sharing a URL space with them. The routes that
act on one device live under ``/api/facilitator/devices`` and this one is addressed by the
team it belongs to, so the two routers have disjoint prefixes and nothing depends on the
order they are mounted in.

Every refusal here is a 404 with one message, whether the team does not exist or is not
the caller's. That is the same rule ENG-443 holds at the claim: a facilitator who could
tell "not yours" from "no such thing" could map an installation by asking about ids, and
closing that at one door and leaving it open at another closes nothing.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.facilitator._deps import FacilitatorUser
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.models.device import TeamDeviceResponse
from app.models.team import TeamFilter, TeamListingResponse
from app.services.device.list_team_devices import list_team_devices
from app.services.project.facilitates_project import facilitates_project
from app.services.project.list_facilitator_teams import list_facilitator_teams

facilitator_teams_router = APIRouter()

TEAM_NOT_FOUND = "Team not found"


@facilitator_teams_router.get("", response_model=TeamListingResponse)
async def list_teams_route(
    user: FacilitatorUser,
    search: str = Query(default="", max_length=200),
    filter: TeamFilter = Query(default=TeamFilter.ALL),
    db: AsyncSession = Depends(get_db),
) -> TeamListingResponse:
    """The facilitator's work queue: their teams, narrowed and already in order.

    The search and the filter are parameters of this route rather than something the Desk
    does to what it received, and the ordering is served for the same reason: the list is a
    work queue and not a catalogue, so who to help next is a product decision and not a
    client's.

    A facilitator with no teams gets a 200 and an empty list. So does a search that matched
    nothing — which is why the answer also carries whether they have any teams at all.
    """
    return await list_facilitator_teams(db, user, search=search, chosen=filter)


@facilitator_teams_router.get("/{team_id}/devices", response_model=list[TeamDeviceResponse])
async def list_team_devices_route(
    team_id: str,
    user: FacilitatorUser,
    db: AsyncSession = Depends(get_db),
) -> list[TeamDeviceResponse]:
    """The devices linked to this team. A team with none answers with an empty list."""
    if not await facilitates_project(db, user, team_id):
        raise NotFoundError(TEAM_NOT_FOUND)

    return [TeamDeviceResponse.of(device) for device in await list_team_devices(db, team_id)]
