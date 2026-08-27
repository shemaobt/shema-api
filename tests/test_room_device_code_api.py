"""ENG-454 — the two calls a tablet makes before it belongs to anyone.

``create_device`` has been complete since ENG-437 and reachable by nothing: no route, no
script, no seed. So the flow the product describes — the tablet shows a code, a facilitator
types it into the Desk, the link comes back to the tablet — has never been able to start,
and the half that spends the code has only ever been exercised against a fixture.

This is the half that hands a tablet a code to display. It carries no credential: the
device credential is issued to the Desk at claim time and stays there until ENG-455.

The shared room key is what opens it, because a tablet nobody has linked yet holds
nothing else. That is the same key every installation carries, and it is exactly as weak
here as it is on every other room route — retiring it is ENG-455's, not this slice's.
"""

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.device import claim_code, create_device

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


async def test_a_device_this_server_never_minted_is_given_a_fresh_one(client):
    response = await client.post(
        f"{PREFIX}/devices/code",
        headers={"X-Room-Key": KEY},
        json={"device_id": "a-device-this-database-never-had"},
    )

    assert response.status_code == 200
    assert response.json()["device_id"] != "a-device-this-database-never-had"
