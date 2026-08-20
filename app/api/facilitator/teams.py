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

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_middleware import get_current_user
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.db.models.auth import User
from app.models.device import TeamDeviceResponse
from app.models.internalization_room import ElementCoverage
from app.services.device.list_team_devices import list_team_devices
from app.services.internalization_room.team_coverage import team_necklace
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


@facilitator_teams_router.get("/{team_id}/coverage", response_model=list[ElementCoverage])
async def read_team_coverage_route(
    team_id: str,
    pericope: str = Query(min_length=1, max_length=120),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ElementCoverage]:
    """This team's necklace for one passage, bead by bead, in the canon's order.

    ``pericope`` is required, and that is a decision rather than an omission. Nothing in this
    codebase yet knows which passage a team is standing on — resolving it is ENG-450, which
    depends on the fourth coverage state and has not landed. Defaulting to
    ``DEFAULT_PERICOPE`` would answer every team about P01 with full confidence, which is the
    exact failure ENG-450 exists to end. When that resolution arrives it belongs in this
    signature and nowhere else: giving the parameter a default computed there is the one
    change, and it breaks no client, because the Desk already sends the passage it is showing.

    The team gate runs first, and the order matters. Both refusals here are 404, but only one
    of them carries a message that names something — so checking the team first means the
    passage's message is read only by a caller already through the gate. A facilitator who
    could tell "not yours" from "no such team" could map an installation by asking about ids;
    that hole is closed at the claim and at the devices list, and leaving it open here would
    close nothing.
    """
    if not await facilitates_project(db, user, team_id):
        raise NotFoundError(TEAM_NOT_FOUND)

    return await team_necklace(db, team_id=team_id, pericope=pericope)
