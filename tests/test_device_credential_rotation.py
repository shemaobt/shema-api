"""ENG-448 — rotating a credential without sending anyone back to the tablet.

A claim needs a facilitator, a code read off a screen, and someone standing in the room.
If that were the only way to replace a credential, then "we think this one leaked" would
cost a trip, and the honest answer to a suspected leak would be to do nothing.

**The rotation overlaps on purpose, and this is the half worth defending.** A dry swap —
issue the new one, forget the old one — is a trap in exactly the setting this product was
built for: `credential.py` already argues there is no expiry because the room has no
reliable network. Under that same argument, a swap whose response is lost leaves the tablet
holding a credential the server has already forgotten, and the room stops until someone
walks in with a claim code. So the old credential keeps working until the new one is *used*,
and that first use is what ends it.

The window is not time-based, and that is deliberate: a clock would end the old credential
on a tablet that never received the new one, which is the failure this design exists to
avoid.
"""

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ProjectRole
from app.services.device import claim_device_as_facilitator, create_device
from tests.baker import make_language, make_project, make_project_user_access, make_user

SELF_URL = "/api/devices/me"
ROTATE_URL = "/api/devices/me/credential"
DEVICE_CREDENTIAL_HEADER = "X-Device-Credential"


@pytest.fixture()
async def client(db_session: AsyncSession):
    from fastapi import FastAPI

    from app.api.devices import devices_router
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    test_app = FastAPI()
    test_app.include_router(devices_router, prefix="/api/devices")
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def a_claimed_device(db: AsyncSession, *, email="fac@example.com") -> tuple[str, str]:
    """Returns (device_id, credential)."""
    user = await make_user(db, email=email)
    language = await make_language(db, name=f"Lang {email}", code=email[:3])
    project = await make_project(db, language.id, name=f"Team {email}")
    await make_project_user_access(db, project.id, user.id, role=ProjectRole.FACILITATOR)
    minted = await create_device(db)
    claimed = await claim_device_as_facilitator(
        db, user=user, code=minted.claim_code, project_id=project.id
    )
    return claimed.device.id, claimed.credential


def headers(credential: str) -> dict[str, str]:
    return {DEVICE_CREDENTIAL_HEADER: credential}


# Behaviour 1 — a new credential, on the strength of the old one alone.


async def test_rotating_issues_a_different_credential_for_the_same_device(client, db_session):
    device_id, old = await a_claimed_device(db_session)

    rotated = await client.post(ROTATE_URL, headers=headers(old))

    assert rotated.status_code == 200, rotated.text
    new = rotated.json()["credential"]
    assert new != old
    assert rotated.json()["device_id"] == device_id


async def test_the_new_credential_authenticates(client, db_session):
    _device_id, old = await a_claimed_device(db_session)

    new = (await client.post(ROTATE_URL, headers=headers(old))).json()["credential"]

    served = await client.get(SELF_URL, headers=headers(new))
    assert served.status_code == 200, served.text


async def test_rotating_needs_a_credential_of_its_own(client):
    """No credential, no rotation — otherwise this route mints one for anybody."""
    refused = await client.post(ROTATE_URL, headers=headers("d" * 64))

    assert refused.status_code == 401


# Behaviour 2 — the overlap: the old one survives until the new one lands.


async def test_the_old_credential_still_works_until_the_new_one_is_used(client, db_session):
    """The lost-response case, which is the whole reason the overlap exists.

    The rotation happened and the tablet never saw the answer. It retries with what it
    still holds, and the room keeps going.
    """
    _device_id, old = await a_claimed_device(db_session)

    rotated = await client.post(ROTATE_URL, headers=headers(old))
    assert rotated.status_code == 200, rotated.text

    served = await client.get(SELF_URL, headers=headers(old))
    assert served.status_code == 200, served.text


async def test_the_first_use_of_the_new_credential_ends_the_old_one(client, db_session):
    """The tablet did receive the answer, and proved it by using it.

    Until that proof arrives two credentials open the same device, which is the cost of
    the overlap. This is what keeps the cost bounded: the window closes on evidence, not
    on a clock that cannot see whether the tablet ever got the message.
    """
    _device_id, old = await a_claimed_device(db_session)
    new = (await client.post(ROTATE_URL, headers=headers(old))).json()["credential"]

    assert (await client.get(SELF_URL, headers=headers(new))).status_code == 200

    refused = await client.get(SELF_URL, headers=headers(old))
    assert refused.status_code == 401


async def test_a_second_rotation_after_a_lost_answer_keeps_the_tablet_alive(client, db_session):
    """Two rotations whose answers both went missing, then one that arrives.

    The tablet still holds nothing but its original credential, so that is what it rotates
    with, twice. What must not happen is the credential in the tablet's hand being retired
    in favour of one that only ever existed in a response nobody received — that is the dry
    swap wearing a different hat.

    The middle credential is the one to watch: nothing holds it, and it must not stay alive
    just because it was once issued.
    """
    _device_id, held = await a_claimed_device(db_session)

    lost = (await client.post(ROTATE_URL, headers=headers(held))).json()["credential"]
    arrived = (await client.post(ROTATE_URL, headers=headers(held))).json()["credential"]

    assert (await client.get(SELF_URL, headers=headers(held))).status_code == 200, (
        "a credencial que o tablet tem na mao parou de valer por causa de uma resposta "
        "que ele nunca recebeu"
    )
    assert (await client.get(SELF_URL, headers=headers(arrived))).status_code == 200
    assert (await client.get(SELF_URL, headers=headers(lost))).status_code == 401
