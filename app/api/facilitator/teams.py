"""The Desk's entry screen and the panels behind it, all addressed by team.

Three reads and no writes. The work queue, the team's necklace for one passage, and the
book's fourteen passages with this team's position on each. Where a team stands is answered
by one resolution (`services/internalization_room/progression.py`) rather than by each route
working it out, which is what "one source of truth for where is this team" costs in practice:
the queue used to read the most recent session that named a passage and the necklace used to
make the caller say, and the two could disagree on a team that had worked a passage over two
evenings.

Nothing here writes, and that is D-03 rather than an omission: the team walks the book on its
own and the facilitator reads. There is no operation in this module that could move a team.

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
from app.core.exceptions import ConflictError, NotFoundError
from app.models.device import TeamDeviceResponse
from app.models.internalization_room import (
    ElementCoverage,
    PericopeStanding,
    TeamSessionResponse,
)
from app.models.team import FacilitatorTeamDetail, TeamFilter, TeamListingResponse
from app.services.device.list_team_devices import list_team_devices
from app.services.internalization_room.progression import active_passage, team_standing
from app.services.internalization_room.team_coverage import team_necklace
from app.services.internalization_room.team_sessions import list_team_sessions
from app.services.project.facilitates_project import facilitates_project
from app.services.project.list_facilitator_teams import list_facilitator_teams
from app.services.project.read_facilitator_team import read_facilitator_team

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


@facilitator_teams_router.get("/{team_id}", response_model=FacilitatorTeamDetail)
async def read_team_route(
    team_id: str,
    user: FacilitatorUser,
    db: AsyncSession = Depends(get_db),
) -> FacilitatorTeamDetail:
    """One team, at the address its three panels already hang off.

    It exists because of the refusal and not because of the cost. The queue answers two
    statements for fourteen teams and two for one, so a client filtering it would pay the same
    — what it cannot do is refuse the way ``/devices``, ``/coverage`` and ``/pericopes`` refuse.
    Those answer 404 with an identical body whether the team is absent or merely not the
    caller's, and an empty list answers neither, nor either of them apart from a filter that
    happened to hide the row. The screen would make four calls and three would refuse.

    It also carries the two facts a queue row must not: ``closed_total`` and
    ``scene_the_team_is_in`` are about **one** team, and on a fourteen-row answer they would be
    fourteen answers to a question nobody asked.
    """
    team = await read_facilitator_team(db, user, team_id)
    if team is None:
        raise NotFoundError(TEAM_NOT_FOUND)

    return team


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


@facilitator_teams_router.get("/{team_id}/coverage", response_model=list[ElementCoverage])
async def read_team_coverage_route(
    team_id: str,
    user: FacilitatorUser,
    pericope: str | None = Query(default=None, min_length=1, max_length=120),
    db: AsyncSession = Depends(get_db),
) -> list[ElementCoverage]:
    """This team's necklace for one passage, bead by bead, in the canon's order.

    ``pericope`` was required when ENG-449 landed, because nothing in this codebase knew which
    passage a team was standing on and a default would have answered every team about the
    first one with full confidence. ENG-450 resolves it, and this is the change that slice
    said belonged here and nowhere else: the parameter keeps its meaning and gains a default
    computed from the team's own history. It breaks no client — the Desk sends the passage it
    is showing, which is what the selector is for — and it makes the omitted case mean "the
    one they are on" rather than "the first one there is".

    Omitted by a team that has closed every passage of the book is a ``ConflictError``. There
    is no passage they are on, so there is nothing for the default to be; the request is well
    formed and the team exists, which rules out 400 and 404, and naming a passage answers it.

    The team gate runs first, and the order matters. Both refusals here are 404, but only one
    of them carries a message that names something — so checking the team first means the
    passage's message is read only by a caller already through the gate. A facilitator who
    could tell "not yours" from "no such team" could map an installation by asking about ids;
    that hole is closed at the claim and at the devices list, and leaving it open here would
    close nothing.
    """
    if not await facilitates_project(db, user, team_id):
        raise NotFoundError(TEAM_NOT_FOUND)

    if pericope is None:
        pericope = await active_passage(db, project_id=team_id)
        if pericope is None:
            raise ConflictError(
                "This team has closed every passage of the book; name the one to read"
            )

    return await team_necklace(db, team_id=team_id, pericope=pericope)


@facilitator_teams_router.get("/{team_id}/pericopes", response_model=list[PericopeStanding])
async def list_team_pericopes_route(
    team_id: str,
    user: FacilitatorUser,
    db: AsyncSession = Depends(get_db),
) -> list[PericopeStanding]:
    """The book's passages in the canon's order, each already placed for this team.

    It answers positions and not a list. A screen given the fourteen and the team's active
    passage would have to work out closed from current from future itself, which is a second
    place deciding where a team stands — and the two would disagree on exactly the cases that
    matter, such as a passage closed out of order.

    Nothing in this family writes. The team walks the book on its own (D-03) and the
    facilitator reads; there is no operation here that could move a team, which is the
    restriction no other test catches because a stray write leaves every screen looking right.
    """
    if not await facilitates_project(db, user, team_id):
        raise NotFoundError(TEAM_NOT_FOUND)

    return await team_standing(db, team_id)


@facilitator_teams_router.get("/{team_id}/sessions", response_model=list[TeamSessionResponse])
async def list_team_sessions_route(
    team_id: str,
    user: FacilitatorUser,
    db: AsyncSession = Depends(get_db),
) -> list[TeamSessionResponse]:
    """The passage's history (RF-06). A team that has never met answers with an empty list.

    An empty history and a team that is not the caller's are different answers on purpose:
    the second is the 404 this module's docstring describes, because a facilitator who could
    tell "not yours" from "no such thing" could map an installation by asking about ids.
    """
    if not await facilitates_project(db, user, team_id):
        raise NotFoundError(TEAM_NOT_FOUND)

    return await list_team_sessions(db, team_id)
