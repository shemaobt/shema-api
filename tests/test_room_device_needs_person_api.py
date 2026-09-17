"""ENG-624 — a tablet with no session says it needs a person, and its team is told.

The only escalation this system had was addressed by a session id. A tablet whose session
the server has forgotten, or whose build broke before it could open one, had nothing to
say and no one to say it to: the room stops and the facilitator two rooms away learns
about it when somebody walks over.

So the halt is recorded on the device, which is the thing that is still there when the
session is not, and it is read where the facilitators of that device's team already look.
Everything below goes in through the tablet's call and comes out through what a
facilitator can read — the row itself is never asserted, because a row nobody can reach is
the defect this slice exists to remove.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room._deps import DEVICE_CREDENTIAL_HEADER
from app.core.enums import ProjectRole
from app.services.device import claim_device_as_facilitator, create_device
from app.services.device.unlink_device import unlink_device
from tests.baker import (
    grant_facilitator_app_role,
    make_language,
    make_project,
    make_project_user_access,
    make_user,
)

IR = "/api/internalization-room"
ROOM_KEY = "sala-de-teste"
ROOM_KEY_HEADER = "X-Room-Key"
QUEUE = f"{IR}/facilitator/sessions"


def needs_person_url(device_id: str) -> str:
    return f"{IR}/devices/{device_id}/needs-person"


def team_devices_url(team_id: str) -> str:
    return f"/api/facilitator/teams/{team_id}/devices"


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    """Both doors on one app: the tablet's and the Desk's.

    The halt is written through one and read through the other, so a test app carrying only
    one of them could not see the thing this slice is: a call the room makes reaching a
    person who is not in it.
    """
    from fastapi import FastAPI

    from app.api.facilitator.teams import facilitator_teams_router
    from app.api.internalization_room import router as room_router
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    monkeypatch.setattr(get_settings(), "internalization_room_api_key", ROOM_KEY, raising=False)

    test_app = FastAPI()
    test_app.include_router(room_router, prefix=IR)
    test_app.include_router(facilitator_teams_router, prefix="/api/facilitator/teams")
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@dataclass(frozen=True)
class Team:
    """A team and the facilitator who reads it. A team is a project in this system."""

    project: object
    user: object
    headers: dict[str, str]


@dataclass(frozen=True)
class Tablet:
    """A claimed device and the credential that lets it name itself."""

    device_id: str
    credential: str


async def a_team(db: AsyncSession, *, code: str) -> Team:
    """A team, its language and the one person who facilitates it.

    ``code`` is the language's, which is three characters and unique across the table, so
    it is what keeps two teams in one test from being the same team by accident.
    """
    from app.services.auth.issue_tokens import issue_tokens

    email = f"facilitador-{code}@example.com"
    user = await make_user(db, email=email)
    language = await make_language(db, name=f"Lingua {code}", code=code)
    project = await make_project(db, language.id, name=f"Equipe {code}")
    await make_project_user_access(db, project.id, user.id, role=ProjectRole.FACILITATOR)
    await grant_facilitator_app_role(db, user.id)
    access, _refresh = await issue_tokens(db, user)
    return Team(project=project, user=user, headers={"Authorization": f"Bearer {access}"})


async def a_tablet(db: AsyncSession, team: Team, *, label: str | None = None) -> Tablet:
    minted = await create_device(db)
    claimed = await claim_device_as_facilitator(
        db, user=team.user, code=minted.claim_code, project_id=team.project.id, label=label
    )
    return Tablet(device_id=claimed.device.id, credential=claimed.credential)


async def halt(client: httpx.AsyncClient, device_id: str, *, credential: str | None = None):
    """The call itself: on the shared key, or as the tablet naming itself."""
    headers = (
        {DEVICE_CREDENTIAL_HEADER: credential}
        if credential is not None
        else {ROOM_KEY_HEADER: ROOM_KEY}
    )
    return await client.post(needs_person_url(device_id), headers=headers)


async def halted_moments(client: httpx.AsyncClient, team: Team) -> dict[str, str | None]:
    """What the team's devices panel says, device by device."""
    listed = await client.get(team_devices_url(team.project.id), headers=team.headers)
    assert listed.status_code == 200, listed.text[:300]
    return {row["device_id"]: row["needs_person_since"] for row in listed.json()}


async def queued_devices(client: httpx.AsyncClient, team: Team) -> list[dict]:
    """The devices half of the person queue, for the facilitator holding ``team``'s headers."""
    answered = await client.get(QUEUE, headers=team.headers)
    assert answered.status_code == 200, answered.text[:300]
    return answered.json()["devices"]


async def open_a_session(client: httpx.AsyncClient, credential: str):
    return await client.post(
        f"{IR}/sessions",
        headers={DEVICE_CREDENTIAL_HEADER: credential},
        json={"pericope": "P03"},
    )


# Case 1 — the halt reaches the team's facilitator.


async def test_a_tablet_that_halts_is_shown_to_the_facilitator_of_its_own_team(client, db_session):
    """One tablet halts; the panel and the queue both name it, and only it.

    The second tablet is not decoration. With one device on the team, a panel that marked
    every row halted would pass, and so would a queue that listed whatever it found.
    """
    team = await a_team(db_session, code="eqa")
    stopped = await a_tablet(db_session, team, label="Tablet da Ana")
    working = await a_tablet(db_session, team)

    asked = await halt(client, stopped.device_id)

    assert asked.status_code == 200, asked.text[:300]
    assert asked.json()["device_id"] == stopped.device_id

    moments = await halted_moments(client, team)
    assert moments[stopped.device_id] is not None
    assert moments[working.device_id] is None

    queued = await queued_devices(client, team)
    assert [row["device_id"] for row in queued] == [stopped.device_id]
    assert queued[0]["label"] == "Tablet da Ana"
    assert queued[0]["since"] == moments[stopped.device_id]


# Case 2 — and nobody else's.


async def test_the_halt_of_one_team_is_not_shown_to_the_facilitator_of_another(client, db_session):
    """B's emptiness only means something beside A's sighting, so both are in one test.

    Read on its own, an empty queue for B passes against a route that shows nobody
    anything. What makes it scoping is the same halt being visible to A in the lines above.
    """
    team_a = await a_team(db_session, code="eqa")
    team_b = await a_team(db_session, code="eqb")
    stopped = await a_tablet(db_session, team_a)

    assert (await halt(client, stopped.device_id)).status_code == 200

    assert [row["device_id"] for row in await queued_devices(client, team_a)] == [stopped.device_id]

    assert await queued_devices(client, team_b) == []
    refused = await client.get(team_devices_url(team_a.project.id), headers=team_b.headers)
    assert refused.status_code == 404


# Case 3 — a device with no team cannot ask.


async def test_a_device_with_no_team_to_reach_is_refused_and_leaves_no_halt(client, db_session):
    """Three refusals, told apart by status alone, and the team's two reads left as they were.

    A device nobody claimed and one taken out of service have no team, so there is no one
    the halt could reach; an id this server never minted has no row at all. The tablet acts
    on the three differently, which is why they are three statuses and not one.

    The working tablet is what the last two lines are about. None of the three refused
    devices can appear in either read whatever the server does with them — an unclaimed one
    belongs to no team and an unlinked one is filtered out of both — so without a device
    that *can* appear, "the facilitator sees no halt" is a sentence about two empty
    collections and cannot fail. What is asserted, and can, is that the team still has its
    row and that row is not halted.
    """
    team = await a_team(db_session, code="eqa")
    working = await a_tablet(db_session, team)
    unclaimed = await create_device(db_session)
    retired = await a_tablet(db_session, team)
    await unlink_device(db_session, user=team.user, device_id=retired.device_id)

    assert (await halt(client, unclaimed.device.id)).status_code == 409
    assert (await halt(client, retired.device_id)).status_code == 409
    assert (await halt(client, str(uuid.uuid4()))).status_code == 404

    assert await halted_moments(client, team) == {working.device_id: None}
    assert await queued_devices(client, team) == []


# Case 4 — a tablet halts only itself.


async def test_a_tablet_naming_itself_may_halt_only_itself(client, db_session):
    """A credential names one device, and here it also bounds what that device may say.

    The shared key names nobody and may halt any claimed device — that window is open until
    ENG-455 retires the key. A tablet that has stopped naming itself has given that up.
    """
    team = await a_team(db_session, code="eqa")
    first = await a_tablet(db_session, team)
    second = await a_tablet(db_session, team)

    reaching_over = await halt(client, second.device_id, credential=first.credential)

    assert reaching_over.status_code == 403
    assert await halted_moments(client, team) == {
        first.device_id: None,
        second.device_id: None,
    }

    itself = await halt(client, first.device_id, credential=first.credential)

    assert itself.status_code == 200, itself.text[:300]
    moments = await halted_moments(client, team)
    assert moments[first.device_id] is not None
    assert moments[second.device_id] is None


# Case 5 — asking twice keeps the first moment.


async def test_a_tablet_asking_twice_does_not_move_the_moment_it_first_asked(client, db_session):
    """The halt is one event, however many times a tablet retries reporting it.

    A retry that restamped the moment would tell the facilitator the room stopped just now,
    every time the tablet asked again — the queue would never age and the oldest halt would
    never be the one at the top.

    Asserted on both ends of the retry: what the tablet is told, which is what makes the
    retry free for it, and what the facilitator reads, which is what the halt is for.
    """
    team = await a_team(db_session, code="eqa")
    stopped = await a_tablet(db_session, team)

    asked = await halt(client, stopped.device_id)
    assert asked.status_code == 200
    first_moment = (await halted_moments(client, team))[stopped.device_id]
    assert first_moment is not None

    again = await halt(client, stopped.device_id)
    assert again.status_code == 200

    assert again.json()["needs_person_since"] == asked.json()["needs_person_since"]
    assert (await halted_moments(client, team))[stopped.device_id] == first_moment


# Case 6 — opening a session lifts it, and only for that device.


async def test_the_halt_lifts_when_that_tablet_opens_a_session_and_not_when_another_does(
    client, db_session
):
    """The room going again is what ends the halt, the way a landing turn ends a session's.

    The second tablet is what makes this about the device and not about the team: a lift
    keyed on the team would clear the halt the moment anybody in the room started anything,
    and the tablet that actually stopped would still be stopped.
    """
    team = await a_team(db_session, code="eqa")
    stopped = await a_tablet(db_session, team)
    other = await a_tablet(db_session, team)

    assert (await halt(client, stopped.device_id)).status_code == 200

    elsewhere = await open_a_session(client, other.credential)
    assert elsewhere.status_code == 200, elsewhere.text[:300]
    assert (await halted_moments(client, team))[stopped.device_id] is not None

    resumed = await open_a_session(client, stopped.credential)
    assert resumed.status_code == 200, resumed.text[:300]

    assert (await halted_moments(client, team))[stopped.device_id] is None
    assert await queued_devices(client, team) == []


# A halted tablet taken out of service leaves the queue with the device.


async def test_a_halted_tablet_taken_out_of_service_leaves_the_queue(client, db_session):
    """The halt outlives the tablet's service unless the queue says otherwise.

    ``unlink_device`` revokes the credential and stamps the moment; it does not clear
    ``project_id``, so the row stays inside the team's scope with its halt still standing.
    A facilitator would keep reading "this tablet needs someone" about a tablet in a drawer,
    and there is no call left that could lift it — the device cannot open a session.

    Not asserted by the case above it: that one is about a halt being **refused**, and it
    passes whether or not the queue filters, because nothing was ever recorded.
    """
    team = await a_team(db_session, code="eqa")
    stopped = await a_tablet(db_session, team)

    assert (await halt(client, stopped.device_id)).status_code == 200
    assert [row["device_id"] for row in await queued_devices(client, team)] == [stopped.device_id]

    await unlink_device(db_session, user=team.user, device_id=stopped.device_id)

    assert await queued_devices(client, team) == []


# The queue is a queue: the newest halt is at the top.


async def test_the_queue_puts_the_newest_halt_first(client, db_session):
    """Two tablets of one team stop, and the facilitator reads them in the order they did.

    Order is the difference between a queue and a set. A facilitator with two rooms waiting
    reads this list to decide which one to walk to, and an order that came out of whatever
    the planner returned would make that decision on nothing.
    """
    team = await a_team(db_session, code="eqa")
    earlier = await a_tablet(db_session, team)
    later = await a_tablet(db_session, team)

    assert (await halt(client, earlier.device_id)).status_code == 200
    assert (await halt(client, later.device_id)).status_code == 200

    queued = await queued_devices(client, team)

    assert [row["device_id"] for row in queued] == [later.device_id, earlier.device_id]


# A session that could not be opened is not a room that went again.


async def test_a_refused_session_request_leaves_the_halt_standing(client, db_session):
    """The lift is evidence the room resumed, so a request that opened nothing lifts nothing.

    Naming a language the room does not speak is refused before any session exists. A lift
    written ahead of the session, or one that treated the attempt as the evidence, would
    clear the halt for a tablet that is still exactly as stuck as it was — and the tablet
    has no way to notice, because it never got a session either.
    """
    team = await a_team(db_session, code="eqa")
    stopped = await a_tablet(db_session, team)

    assert (await halt(client, stopped.device_id)).status_code == 200

    refused = await client.post(
        f"{IR}/sessions",
        headers={DEVICE_CREDENTIAL_HEADER: stopped.credential},
        json={"pericope": "P03", "language": "xx"},
    )

    assert refused.status_code != 200, refused.text[:300]
    assert (await halted_moments(client, team))[stopped.device_id] is not None
