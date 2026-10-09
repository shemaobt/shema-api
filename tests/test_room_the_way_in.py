"""ENG-1518 — the way into the room is a claim code linked from the Desk and a device credential.

A team door opens only to the credential a tablet collected after its claim code was spent,
and only while the tablet's team exists. The three claim doors open to anyone, because the
code is only worth what a facilitator spends on it. The shared room key opens nothing.
"""

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room._deps import DEVICE_CREDENTIAL_HEADER
from app.services.internalization_room import sessions as room_sessions
from tests.device_harness import a_linked_tablet
from tests.release_harness import PREFIX
from tests.room_harness import room_client


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    async with room_client(db_session, monkeypatch) as c:
        yield c


async def open_a_session(client: httpx.AsyncClient, headers: dict[str, str]) -> httpx.Response:
    return await client.post(f"{PREFIX}/sessions", headers=headers, json={"pericope": "OV"})


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
