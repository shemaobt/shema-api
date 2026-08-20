"""What a team has: the Desk's devices panel, addressed by team.

Split from the device routes rather than sharing a URL space with them. The routes that
act on one device live under ``/api/facilitator/devices`` and this one is addressed by the
team it belongs to, so the two routers have disjoint prefixes and nothing depends on the
order they are mounted in.

Every refusal here is a 404 with one message, whether the team does not exist or is not
the caller's. That is the same rule ENG-443 holds at the claim: a facilitator who could
tell "not yours" from "no such thing" could map an installation by asking about ids, and
closing that at one door and leaving it open at another closes nothing.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_middleware import get_current_user
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.db.models.auth import User
from app.models.device import TeamDeviceResponse
from app.models.internalization_room import TeamSessionResponse
from app.services.device.list_team_devices import list_team_devices
from app.services.internalization_room.team_sessions import list_team_sessions
from app.services.project.facilitates_project import facilitates_project

facilitator_teams_router = APIRouter()

TEAM_NOT_FOUND = "Team not found"


@facilitator_teams_router.get("/{team_id}/devices", response_model=list[TeamDeviceResponse])
async def list_team_devices_route(
    team_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[TeamDeviceResponse]:
    """The devices linked to this team. A team with none answers with an empty list."""
    if not await facilitates_project(db, user, team_id):
        raise NotFoundError(TEAM_NOT_FOUND)

    return [TeamDeviceResponse.of(device) for device in await list_team_devices(db, team_id)]


@facilitator_teams_router.get("/{team_id}/sessions", response_model=list[TeamSessionResponse])
async def list_team_sessions_route(
    team_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[TeamSessionResponse]:
    """The passage's history (RF-06). A team that has never met answers with an empty list.

    An empty history and a team that is not the caller's are different answers on purpose:
    the second is the 404 this module's docstring describes, because a facilitator who could
    tell "not yours" from "no such thing" could map an installation by asking about ids.
    """
    if not await facilitates_project(db, user, team_id):
        raise NotFoundError(TEAM_NOT_FOUND)

    return await list_team_sessions(db, team_id)
