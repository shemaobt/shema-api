"""ENG-1518 — the way into the room is a claim code linked from the Desk and a device credential.

A team door opens only to the credential a tablet collected after its claim code was spent,
and only while the tablet's team exists. The three claim doors open to anyone, because the
code is only worth what a facilitator spends on it. The shared room key opens nothing.
"""

import httpx
import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room._deps import DEVICE_CREDENTIAL_HEADER
from app.core.enums import ProjectRole
from app.core.exceptions import AuthenticationError
from app.db.models.internalization_room import IRSession
from app.services.device import claim_device_as_facilitator, create_device
from app.services.device.unlink_device import unlink_device
from app.services.internalization_room import sessions as room_sessions
from app.services.internalization_room.turn_dedup import remember_turn
from tests.baker import make_project_user_access, make_user
from tests.device_harness import RETIRED_ROOM_KEY_HEADER, LinkedTablet, a_linked_tablet
from tests.release_harness import PREFIX
from tests.room_harness import room_client

RETIRED_KEY = "sala-de-teste"
KEY_ALONE = {RETIRED_ROOM_KEY_HEADER: RETIRED_KEY}
UNKNOWN = {DEVICE_CREDENTIAL_HEADER: "b" * 64}

#: Every door under the room prefix a tablet calls once it belongs to a team, with the
#: device needs-person door and the voice route.
TEAM_DOORS = [
    ("GET", "/books/{book}/passages"),
    ("POST", "/devices/{device_id}/needs-person"),
    ("GET", "/fixed-lines/{line}"),
    ("POST", "/questions"),
    ("GET", "/questions/audio/{handle}"),
    ("GET", "/questions/replies"),
    ("POST", "/questions/{question_id}/heard"),
    ("POST", "/sessions"),
    ("GET", "/sessions/{session_id}"),
    ("POST", "/sessions/{session_id}/back-translation/chunks"),
    ("POST", "/sessions/{session_id}/back-translation/finish"),
    ("GET", "/sessions/{session_id}/coverage"),
    ("POST", "/sessions/{session_id}/needs-person"),
    ("POST", "/sessions/{session_id}/person-arrived"),
    ("POST", "/sessions/{session_id}/release"),
    ("POST", "/sessions/{session_id}/segments/{segment_id}/divide"),
    ("POST", "/sessions/{session_id}/segments/{segment_id}/replace"),
    ("GET", "/sessions/{session_id}/takes"),
    ("POST", "/sessions/{session_id}/takes"),
    ("GET", "/sessions/{session_id}/takes/{take_id}/audio"),
    ("POST", "/sessions/{session_id}/turns"),
    ("GET", "/sessions/{session_id}/turns/{turn_id}"),
    ("GET", "/voice/{handle}"),
]


#: The three doors a tablet calls before it belongs to a team, open to anyone.
CLAIM_DOORS = [
    ("POST", "/devices/code"),
    ("GET", "/devices/{device_id}/link"),
    ("POST", "/devices/{device_id}/credential"),
]

#: The doors under the prefix that are neither the team's nor the claim's: a facilitator
#: signs in to the first, the golden runner presents its own key to the other two.
NOT_THE_TABLETS = ("/facilitator/", "/golden/", "/text-seam/")


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    """The room's doors with no caller of their own: every case says who is knocking."""
    async with room_client(db_session, monkeypatch) as c:
        del c.headers[DEVICE_CREDENTIAL_HEADER]
        del c.headers["X-Room-Device"]
        yield c


async def open_a_session(client: httpx.AsyncClient, headers: dict[str, str]) -> httpx.Response:
    return await client.post(f"{PREFIX}/sessions", headers=headers, json={"pericope": "OV"})


async def sessions_held(db: AsyncSession) -> int:
    return (await db.execute(select(func.count()).select_from(IRSession))).scalar_one()


async def a_facilitator_of_a_team(db: AsyncSession) -> tuple:
    tablet = await a_linked_tablet(db)
    user = await make_user(db, email=f"fac-{tablet.device_id[:8]}@example.com")
    await make_project_user_access(db, tablet.project_id, user.id, role=ProjectRole.FACILITATOR)
    return user, tablet.project_id


def knock(client: httpx.AsyncClient, method: str, path: str, headers: dict[str, str]):
    filled = path.format(
        book="Ruth",
        device_id="aparelho",
        line="A-1",
        handle="nada",
        question_id="pergunta",
        session_id="sessao",
        segment_id="trecho",
        take_id="tomada",
        turn_id="turno",
    )
    return client.request(method, f"{PREFIX}{filled}", headers=headers)


# 1


async def test_a_session_is_refused_to_a_caller_with_the_room_key_and_no_credential(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    refused = await open_a_session(client, KEY_ALONE)

    assert refused.status_code == 401, refused.text
    assert await sessions_held(db_session) == 0


# 2


async def test_a_session_opens_for_a_linked_tablet_in_its_own_team(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    tablet = await a_linked_tablet(db_session)

    opened = await open_a_session(client, tablet.headers)

    assert opened.status_code == 200, opened.text
    session = await room_sessions.get_session(db_session, opened.json()["session_id"])
    assert session.project_id == tablet.project_id


# 3


async def test_a_claim_code_is_minted_with_no_header(client: httpx.AsyncClient) -> None:
    minted = await client.post(f"{PREFIX}/devices/code", json={})

    assert minted.status_code == 200, minted.text
    assert minted.json()["code"]


# 4


async def test_the_link_is_read_and_the_credential_collected_with_no_header(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    facilitator, team_id = await a_facilitator_of_a_team(db_session)
    shown = (await client.post(f"{PREFIX}/devices/code", json={})).json()
    never_claimed = (await client.post(f"{PREFIX}/devices/code", json={})).json()["device_id"]
    device_id = shown["device_id"]

    unspent = await client.get(f"{PREFIX}/devices/{device_id}/link")
    await claim_device_as_facilitator(
        db_session, user=facilitator, code=shown["code"], project_id=team_id
    )
    linked = await client.get(f"{PREFIX}/devices/{device_id}/link")
    collected = await client.post(f"{PREFIX}/devices/{device_id}/credential")
    again = await client.post(f"{PREFIX}/devices/{device_id}/credential")
    unclaimed = await client.post(f"{PREFIX}/devices/{never_claimed}/credential")
    unknown_link = await client.get(f"{PREFIX}/devices/nunca-houve/link")
    unknown_collect = await client.post(f"{PREFIX}/devices/nunca-houve/credential")

    assert unspent.status_code == 204, unspent.text
    assert linked.status_code == 200, linked.text
    assert collected.status_code == 200, collected.text
    assert collected.json()["credential"]
    assert again.status_code == 403, again.text
    assert unclaimed.status_code == 409, unclaimed.text
    assert unknown_link.status_code == 404, unknown_link.text
    assert unknown_collect.status_code == 404, unknown_collect.text


# 5


async def test_the_device_needs_person_door_refuses_the_key_alone(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    tablet = await a_linked_tablet(db_session)

    refused = await client.post(
        f"{PREFIX}/devices/{tablet.device_id}/needs-person", headers=KEY_ALONE
    )

    assert refused.status_code == 401, refused.text


# 6


async def test_the_device_needs_person_door_refuses_another_tablets_credential(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    halted = await a_linked_tablet(db_session)
    other = await a_linked_tablet(db_session, team_id=halted.project_id)

    own = await client.post(
        f"{PREFIX}/devices/{halted.device_id}/needs-person", headers=halted.headers
    )
    refused = await client.post(
        f"{PREFIX}/devices/{halted.device_id}/needs-person", headers=other.headers
    )

    assert own.status_code == 200, own.text
    assert refused.status_code == 403, refused.text
    assert refused.json()["detail"] == "A device may only ask for a person for itself."


# 7


async def test_a_tablet_unlinked_from_the_desk_is_refused_with_device_revoked_on_a_team_door(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    facilitator, team_id = await a_facilitator_of_a_team(db_session)
    tablet = await a_linked_tablet(db_session, team_id=team_id, facilitator=facilitator)
    await unlink_device(db_session, user=facilitator, device_id=tablet.device_id)

    refused = await open_a_session(client, tablet.headers)

    assert refused.status_code == 403, refused.text
    assert refused.json()["code"] == "DEVICE_REVOKED"


# 8


async def test_a_linked_tablet_whose_team_is_gone_is_refused_on_a_team_door(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    tablet = await a_linked_tablet(db_session)
    await db_session.execute(text("DELETE FROM projects WHERE id = :id"), {"id": tablet.project_id})
    await db_session.commit()
    db_session.expire_all()

    refused = await open_a_session(client, tablet.headers)
    unknown = await open_a_session(client, UNKNOWN)

    assert refused.status_code == 401, refused.text
    assert refused.json() == unknown.json()
    assert await sessions_held(db_session) == 0


# 9


async def test_a_session_with_no_team_is_reached_by_no_room_caller(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    tablet = await a_linked_tablet(db_session)
    own = await room_sessions.create_session(
        db_session, pericope="P01", project_id=tablet.project_id
    )
    teamless = await room_sessions.create_session(db_session, pericope="P01")
    theirs = await room_sessions.create_session(db_session, pericope="P01", project_id="outra")
    answered = {
        "session_id": teamless.id,
        "turn_id": "t-1",
        "done": False,
        "coverage": {
            "engaged": 0,
            "surfaced": 0,
            "total": 0,
            "absence_index": 0,
            "beads_total": 0,
            "beads_filled": 0,
        },
    }
    await remember_turn(db_session, session_id=teamless.id, turn_id="t-1", response=answered)

    own_read = await client.get(f"{PREFIX}/sessions/{own.id}", headers=tablet.headers)
    read = await client.get(f"{PREFIX}/sessions/{teamless.id}", headers=tablet.headers)
    their_read = await client.get(f"{PREFIX}/sessions/{theirs.id}", headers=tablet.headers)
    turn = await client.post(
        f"{PREFIX}/sessions/{teamless.id}/turns", headers=tablet.headers, data={"turn_id": "t-1"}
    )

    assert own_read.status_code == 200, own_read.text
    assert read.status_code == 404, read.text
    assert their_read.status_code == 404, their_read.text
    assert read.json()["code"] == their_read.json()["code"]
    assert read.json()["detail"].replace(teamless.id, "X") == their_read.json()["detail"].replace(
        theirs.id, "X"
    )
    assert turn.status_code == 404, turn.text


# 10


@pytest.mark.parametrize(("method", "path"), TEAM_DOORS)
async def test_every_team_door_refuses_a_caller_with_the_key_alone(
    client: httpx.AsyncClient, method: str, path: str
) -> None:
    refused = await knock(client, method, path, KEY_ALONE)

    assert refused.status_code == 401, refused.text


def test_the_door_tables_are_every_door_a_tablet_can_call() -> None:
    from app.main import app

    doors = {
        (method, route.path.removeprefix(PREFIX))
        for route in app.routes
        if getattr(route, "path", "").startswith(f"{PREFIX}/")
        and not route.path.removeprefix(PREFIX).startswith(NOT_THE_TABLETS)
        for method in route.methods - {"HEAD", "OPTIONS"}
    }

    assert doors == set(TEAM_DOORS) | set(CLAIM_DOORS)


@pytest.mark.parametrize(("method", "path"), TEAM_DOORS)
async def test_every_team_door_lets_a_linked_tablet_past_the_gate(
    client: httpx.AsyncClient, db_session: AsyncSession, method: str, path: str
) -> None:
    tablet = await a_linked_tablet(db_session)

    let_in = await knock(client, method, path, tablet.headers)

    assert let_in.status_code != 401, let_in.text


# 11


@pytest.mark.parametrize(("method", "path"), TEAM_DOORS)
async def test_every_team_door_refuses_a_caller_with_no_header(
    client: httpx.AsyncClient, method: str, path: str
) -> None:
    refused = await knock(client, method, path, {})

    assert refused.status_code == 401, refused.text


# 12


async def test_the_voice_route_opens_to_a_linked_tablet_and_to_nothing_else(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    tablet = await a_linked_tablet(db_session)

    let_in = await client.get(f"{PREFIX}/voice/nada", headers=tablet.headers)
    keyed = await client.get(f"{PREFIX}/voice/nada", headers=KEY_ALONE)

    assert let_in.status_code == 404, let_in.text
    assert keyed.status_code == 401, keyed.text


# 13


async def test_the_harness_builders_tablet_is_claimed_and_collected(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    tablet = await a_linked_tablet(db_session)

    opened = await open_a_session(client, tablet.headers)
    desks_copy = await open_a_session(client, {DEVICE_CREDENTIAL_HEADER: tablet.desk_copy})

    assert opened.status_code == 200, opened.text
    session = await room_sessions.get_session(db_session, opened.json()["session_id"])
    assert session.project_id == tablet.project_id
    assert desks_copy.status_code == 401, desks_copy.text


# 13a


async def test_a_claimed_tablet_that_never_collected_is_refused_on_a_team_door(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    facilitator, team_id = await a_facilitator_of_a_team(db_session)
    minted = await create_device(db_session)
    claimed = await claim_device_as_facilitator(
        db_session, user=facilitator, code=minted.claim_code, project_id=team_id
    )

    refused = await open_a_session(client, {DEVICE_CREDENTIAL_HEADER: claimed.credential})
    unknown = await open_a_session(client, UNKNOWN)

    assert refused.status_code == 401, refused.text
    assert refused.json() == unknown.json()


# 14


async def test_a_device_gets_in_with_a_collected_credential_and_a_team_only(
    db_session: AsyncSession,
) -> None:
    from app.api.internalization_room._deps import linked_tablet

    tablet = await a_linked_tablet(db_session)
    teamless: LinkedTablet = await a_linked_tablet(db_session)
    await db_session.execute(
        text("DELETE FROM projects WHERE id = :id"), {"id": teamless.project_id}
    )
    await db_session.commit()
    db_session.expire_all()

    let_in = await linked_tablet(db_session, x_device_credential=tablet.credential)

    assert let_in.id == tablet.device_id
    for refused in (teamless.credential, "b" * 64, None):
        with pytest.raises(AuthenticationError):
            await linked_tablet(db_session, x_device_credential=refused)
