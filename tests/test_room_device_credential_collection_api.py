"""ENG-622 — the call a claimed tablet makes once, to stop depending on the shared key.

Until now the credential a claim mints went to the Desk and stopped there: the row keeps
only a hash, the plaintext rode back in the claim response, and `git grep credential` in
`facilitator-desk` finds nothing that reads it. So the one party that needs a credential —
the tablet — has never had a way to hold one, and every room route it calls is opened by
the string every installation shares.

This is that way. A tablet that has been claimed asks once, receives a credential minted
for the occasion, and from then on names itself on every request. The claim-time copy the
Desk was handed stops working at that moment, which is the point rather than a side
effect: one device, one live credential, and the copy nobody used is not left live.

Once, and the refusals say which "no" it is. A tablet that asks before anyone has claimed
it must keep polling; a tablet that already collected must stop and show a new claim code.
A single refusal for both leaves the app unable to choose, and choosing wrong either
strands a tablet on a dead poll or wipes one that is working.

The shared room key opens this route, like the two beside it, because a tablet with no
credential is exactly the caller it exists to serve. Retiring the key is ENG-455's.
"""

import asyncio
from dataclasses import dataclass

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.internalization_room._deps import DEVICE_CREDENTIAL_HEADER
from app.core.enums import ProjectRole
from app.services.device import claim_device_as_facilitator, create_device
from app.services.device.get_device import get_device
from app.services.device.rotate_device_credential import rotate_device_credential
from app.services.device.unlink_device import unlink_device
from tests.baker import make_language, make_project, make_project_user_access, make_user

PREFIX = "/api/internalization-room"
KEY = "sala-de-teste"
ROOM_KEY_HEADER = "X-Room-Key"


def _app_for(session: AsyncSession):
    from fastapi import FastAPI

    from app.api.internalization_room import router
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    test_app = FastAPI()
    test_app.include_router(router, prefix=PREFIX)
    register_exception_handlers(test_app)

    async def _get_db():
        yield session

    test_app.dependency_overrides[get_db] = _get_db
    return test_app


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "internalization_room_api_key", KEY, raising=False)

    transport = ASGITransport(app=_app_for(db_session))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@dataclass(frozen=True)
class Tablet:
    """A claimed device, the facilitator who claimed it, and the copy the Desk received."""

    user: object
    project: object
    device_id: str
    claim_time_credential: str


async def a_claimed_device(db: AsyncSession, *, email: str = "fac@example.com") -> Tablet:
    user = await make_user(db, email=email)
    language = await make_language(db, name=f"Lang {email}", code=email[:3])
    project = await make_project(db, language.id, name=f"Team {email}")
    await make_project_user_access(db, project.id, user.id, role=ProjectRole.FACILITATOR)
    minted = await create_device(db)
    claimed = await claim_device_as_facilitator(
        db, user=user, code=minted.claim_code, project_id=project.id
    )
    return Tablet(
        user=user,
        project=project,
        device_id=claimed.device.id,
        claim_time_credential=claimed.credential,
    )


async def collect(client, device_id: str):
    """The call under test, made the way a tablet makes it: with the shared key."""
    return await client.post(
        f"{PREFIX}/devices/{device_id}/credential", headers={ROOM_KEY_HEADER: KEY}
    )


async def read_the_link_with(client, device_id: str, credential: str):
    """A room route answered with the credential alone — no shared key in the request."""
    return await client.get(
        f"{PREFIX}/devices/{device_id}/link", headers={DEVICE_CREDENTIAL_HEADER: credential}
    )


async def test_a_claimed_tablet_receives_a_credential_it_can_use(client, db_session):
    tablet = await a_claimed_device(db_session)

    collected = await collect(client, tablet.device_id)

    assert collected.status_code == 200, collected.text
    credential = collected.json()["credential"]
    served = await read_the_link_with(client, tablet.device_id, credential)
    assert served.status_code == 200, served.text
    assert served.json()["project_id"] == tablet.project.id


async def test_the_second_collection_is_refused_and_the_first_credential_still_works(
    client, db_session
):
    """A lost response must not cost the tablet the credential it already received.

    Asserting the refusal alone would pass against a route that quietly minted a second
    credential and threw the first away. What makes this exactly-once is the line below
    it: the credential from the first call still opens the door afterwards.
    """
    tablet = await a_claimed_device(db_session)
    first = (await collect(client, tablet.device_id)).json()["credential"]

    again = await collect(client, tablet.device_id)

    assert again.status_code == 403
    assert "credential" not in again.json()
    served = await read_the_link_with(client, tablet.device_id, first)
    assert served.status_code == 200, served.text


async def test_a_tablet_nobody_has_claimed_is_refused_and_told_so_differently(client, db_session):
    """409, and the second collection above is 403, because the tablet acts on them apart.

    Nobody has claimed this one yet, which is the whole stretch a tablet spends showing a
    code — it should keep polling. A tablet that already collected must stop polling and
    show a new code instead. One status for both is an app that cannot choose.
    """
    showing_a_code = await create_device(db_session)

    refused = await collect(client, showing_a_code.device.id)

    assert refused.status_code == 409
    assert "credential" not in refused.json()


async def test_a_tablet_taken_out_of_service_gets_nothing(client, db_session):
    """The same 409 a tablet nobody claimed gets, because ``link`` already treats them alike.

    Naming the status is what lets this case fail. "Refused, whatever the status" is
    satisfied by a route that does not exist — a 404 is not 200 and carries no credential
    — so the looser wording could never have gone red before the route was written.
    """
    tablet = await a_claimed_device(db_session)

    await unlink_device(db_session, user=tablet.user, device_id=tablet.device_id)

    refused = await collect(client, tablet.device_id)

    assert refused.status_code == 409
    assert "credential" not in refused.json()


async def test_collecting_retires_the_copy_the_desk_was_handed(client, db_session):
    """The claim response's credential works right up until the tablet collects, then not.

    The 200 before the collection is what makes the refusal after it mean retirement
    rather than a string that was never good.
    """
    tablet = await a_claimed_device(db_session)
    before = await read_the_link_with(client, tablet.device_id, tablet.claim_time_credential)
    assert before.status_code == 200, before.text

    await collect(client, tablet.device_id)

    after = await read_the_link_with(client, tablet.device_id, tablet.claim_time_credential)
    assert after.status_code != 200


async def test_a_device_id_this_server_does_not_know_is_missing_not_unclaimed(client):
    refused = await collect(client, "a-device-this-database-never-had")

    assert refused.status_code == 404
    assert refused.json()["detail"] == "No device with that id."


async def test_two_first_calls_at_once_issue_one_credential(client, db_session, test_engine):
    """Two tablets cannot exist, but two retries racing each other can.

    Driven on two sessions rather than one, because a single session serialises the two
    calls and would pass against a check-then-write with no guard on it — the very shape
    this asserts against.
    """
    tablet = await a_claimed_device(db_session)
    factory = async_sessionmaker(
        test_engine, expire_on_commit=False, class_=AsyncSession, autoflush=False
    )

    async with (
        factory() as one,
        factory() as two,
        httpx.AsyncClient(
            transport=ASGITransport(app=_app_for(one)), base_url="http://test"
        ) as first_caller,
        httpx.AsyncClient(
            transport=ASGITransport(app=_app_for(two)), base_url="http://test"
        ) as second_caller,
    ):
        answers = await asyncio.gather(
            collect(first_caller, tablet.device_id),
            collect(second_caller, tablet.device_id),
        )

    assert sorted(answer.status_code for answer in answers) == [200, 403]
    issued = next(answer for answer in answers if answer.status_code == 200).json()["credential"]
    served = await read_the_link_with(client, tablet.device_id, issued)
    assert served.status_code == 200, served.text


async def test_collecting_retires_the_desks_copy_even_after_it_was_rotated(client, db_session):
    """The copy the Desk holds is a credential like any other, and can be traded for a newer.

    Nothing in ``facilitator-desk`` does that today, which is why the case above is the one
    the issue describes. But a rotation deliberately keeps the credential that was presented
    alive — it parks its hash in the row, and the door reads that hash too — so a collection
    that replaced only the current hash would leave the Desk holding a string that still
    opens the door, which is exactly what collecting is supposed to end.
    """
    tablet = await a_claimed_device(db_session)
    device = await get_device(db_session, tablet.device_id)
    assert device is not None
    newer = await rotate_device_credential(
        db_session, device, presented=tablet.claim_time_credential
    )

    await collect(client, tablet.device_id)

    for retired in (tablet.claim_time_credential, newer):
        refused = await read_the_link_with(client, tablet.device_id, retired)
        assert refused.status_code != 200, refused.text
