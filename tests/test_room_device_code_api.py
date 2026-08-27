"""ENG-454 — the two calls a tablet makes before it belongs to anyone.

``create_device`` has been complete since ENG-437 and reachable by nothing: no route, no
script, no seed. So the flow the product describes — the tablet shows a code, a facilitator
types it into the Desk, the link comes back to the tablet — has never been able to start,
and the half that spends the code has only ever been exercised against a fixture.

These two routes are the tablet's half. The first hands a tablet a code to display; the
second is what it polls until a facilitator has spent it. Neither carries a credential: the
device credential is issued to the Desk at claim time and stays there until ENG-455.

The shared room key is what opens both, because a tablet nobody has linked yet holds
nothing else. That is the same key every installation carries, and it is exactly as weak
here as it is on every other room route — retiring it is ENG-455's, not this slice's.
"""

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.device import claim_code, claim_device, create_device
from tests.baker import make_language, make_project

PREFIX = "/api/internalization-room"
KEY = "sala-de-teste"


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    from fastapi import FastAPI

    from app.api.internalization_room import router
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    monkeypatch.setattr(get_settings(), "internalization_room_api_key", KEY, raising=False)

    test_app = FastAPI()
    test_app.include_router(router, prefix=PREFIX)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def a_team(db: AsyncSession):
    language = await make_language(db, name="Terena", code="ter")
    return await make_project(db, language.id, name="Equipe Terena")


async def test_a_tablet_nobody_has_linked_is_given_a_device_and_a_code_to_show(client):
    response = await client.post(f"{PREFIX}/devices/code", headers={"X-Room-Key": KEY})

    assert response.status_code == 200
    body = response.json()
    assert body["device_id"]
    head, _, tail = body["code"].partition("-")
    assert len(head) == 3 and len(tail) == 4
    assert set(body["code"]) <= set(claim_code.CLAIM_CODE_ALPHABET) | {"-"}
    assert datetime.fromisoformat(body["expires_at"]) > datetime.now(UTC)


async def test_the_shared_room_key_is_what_opens_the_route(client):
    response = await client.post(f"{PREFIX}/devices/code")

    assert response.status_code == 401


async def test_a_code_that_expired_is_redrawn_onto_the_device_that_showed_it(client, db_session):
    minted = await create_device(db_session)
    minted.device.claim_code_expires_at = datetime.now(UTC) - timedelta(minutes=1)
    await db_session.commit()

    response = await client.post(
        f"{PREFIX}/devices/code",
        headers={"X-Room-Key": KEY},
        json={"device_id": minted.device.id},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["device_id"] == minted.device.id
    assert body["code"] != minted.claim_code
    assert datetime.fromisoformat(body["expires_at"]) > datetime.now(UTC)


async def test_a_redraw_whose_code_collides_is_drawn_again(client, db_session, monkeypatch):
    already_out_there = await create_device(db_session)
    mine = await create_device(db_session)
    mine.device.claim_code_expires_at = datetime.now(UTC) - timedelta(minutes=1)
    await db_session.commit()

    drawn = iter([already_out_there.claim_code, "PPP-QQQQ"])
    monkeypatch.setattr(claim_code, "generate_claim_code", lambda: next(drawn))

    response = await client.post(
        f"{PREFIX}/devices/code",
        headers={"X-Room-Key": KEY},
        json={"device_id": mine.device.id},
    )
    monkeypatch.undo()

    assert response.status_code == 200
    assert response.json()["code"] == "PPP-QQQQ"


async def test_a_device_this_server_never_minted_is_given_a_fresh_one(client):
    response = await client.post(
        f"{PREFIX}/devices/code",
        headers={"X-Room-Key": KEY},
        json={"device_id": "a-device-this-database-never-had"},
    )

    assert response.status_code == 200
    assert response.json()["device_id"] != "a-device-this-database-never-had"


async def test_a_device_nobody_has_claimed_yet_answers_that_it_has_no_team(client, db_session):
    minted = await create_device(db_session)

    response = await client.get(
        f"{PREFIX}/devices/{minted.device.id}/link", headers={"X-Room-Key": KEY}
    )

    assert response.status_code == 204


async def test_a_claimed_device_learns_its_team_without_anyone_typing_into_it(client, db_session):
    project = await a_team(db_session)
    minted = await create_device(db_session, label="back shelf")
    await claim_device(db_session, code=minted.claim_code, project_id=project.id)

    response = await client.get(
        f"{PREFIX}/devices/{minted.device.id}/link", headers={"X-Room-Key": KEY}
    )

    assert response.status_code == 200
    assert response.json() == {"project_id": project.id, "label": "back shelf"}


async def test_a_device_taken_out_of_service_has_no_team_to_report(client, db_session):
    project = await a_team(db_session)
    minted = await create_device(db_session)
    await claim_device(db_session, code=minted.claim_code, project_id=project.id)
    minted.device.unlinked_at = datetime.now(UTC)
    await db_session.commit()

    response = await client.get(
        f"{PREFIX}/devices/{minted.device.id}/link", headers={"X-Room-Key": KEY}
    )

    assert response.status_code == 204


async def test_a_device_id_this_server_does_not_know_is_not_a_link_it_is_missing(client):
    response = await client.get(f"{PREFIX}/devices/nothing-here/link", headers={"X-Room-Key": KEY})

    assert response.status_code == 404
    assert response.json()["detail"] == "No device with that id."
