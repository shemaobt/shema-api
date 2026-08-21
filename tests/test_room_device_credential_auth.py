"""ENG-448 — the room app authenticates as a device, not with a key everyone shares.

`X-Room-Key` is one string, the same in every installation, shipped as an asset inside the
bundle. Leak one and you have leaked all of them, and there is nothing to revoke because
there is nothing that tells two tablets apart.

The credential issued at claim is the opposite on both counts: it names one device row, and
nulling its hash ends it. What this file asserts is that the room's door accepts it, that
ending it is felt on the very next request, and that a caller can tell "revoked" from
"wrong" — because those are two different things for the tablet to do about it.

**The shared key is still accepted here, deliberately.** Retiring it is the other half of
the issue and it is not in this slice: the room app does not send the credential until
ENG-455, so a door that took only the credential would open for nobody. Behaviour 3 is that
window, written as a test so that closing it later is a test that changes, not a discovery.
"""

from dataclasses import dataclass

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room._deps import DEVICE_CREDENTIAL_HEADER
from app.core.enums import ProjectRole
from app.services.device import claim_device_as_facilitator, create_device
from app.services.device.unlink_device import unlink_device
from app.services.internalization_room import sessions as room_sessions
from tests.baker import make_language, make_project, make_project_user_access, make_user

PREFIX = "/api/internalization-room"
KEY = "sala-de-teste"
ROOM_KEY_HEADER = "X-Room-Key"


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


@dataclass(frozen=True)
class Tablet:
    """A claimed device, plus the facilitator who can unlink it."""

    user: object
    project: object
    device_id: str
    credential: str


async def a_claimed_device(db: AsyncSession, *, email="fac@example.com") -> Tablet:
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
        credential=claimed.credential,
    )


async def open_a_session(client, headers: dict[str, str]):
    return await client.post(f"{PREFIX}/sessions", headers=headers, json={"pericope": "OV"})


# Behaviour 1 — the credential alone opens the door, and says which project.


async def test_a_credential_alone_is_served_and_scopes_the_session_to_its_project(
    client, db_session
):
    """No `X-Room-Key` in this request at all — the credential is the whole authentication."""
    device = await a_claimed_device(db_session)

    opened = await open_a_session(client, {DEVICE_CREDENTIAL_HEADER: device.credential})

    assert opened.status_code == 200, opened.text
    session = await room_sessions.get_session(db_session, opened.json()["session_id"])
    assert session.project_id == device.project.id


# Behaviour 2 — revocation is felt on the next request, and it is legible.


async def test_a_revoked_credential_is_refused_on_its_very_next_request(client, db_session):
    """The same credential, served and then refused, with only the unlink in between.

    Asserting the refusal alone would pass against a credential that never worked. What
    makes this revocation and not a typo is the 200 above it.
    """
    device = await a_claimed_device(db_session)
    headers = {DEVICE_CREDENTIAL_HEADER: device.credential}

    assert (await open_a_session(client, headers)).status_code == 200

    await unlink_device(db_session, user=device.user, device_id=device.device_id)

    refused = await open_a_session(client, headers)
    assert refused.status_code == 403


async def test_a_revoked_credential_is_told_apart_from_one_that_was_never_issued(
    client, db_session
):
    """Two refusals the tablet has to act on differently.

    A revoked device has to forget its credential and show its claim code again. A device
    holding a string that was never a credential has a bug, not a revocation, and must not
    wipe itself over one. Answering both identically leaves the app unable to choose.
    """
    device = await a_claimed_device(db_session)
    await unlink_device(db_session, user=device.user, device_id=device.device_id)

    revoked = await open_a_session(client, {DEVICE_CREDENTIAL_HEADER: device.credential})
    never_issued = await open_a_session(client, {DEVICE_CREDENTIAL_HEADER: "b" * 64})

    assert revoked.status_code != never_issued.status_code
    assert revoked.json()["code"] != never_issued.json()["code"]


# Behaviour 3 — the window: the shared key is still accepted, and nothing is not.


async def test_the_shared_room_key_is_still_accepted_while_the_window_is_open(client):
    """Deliberate, and dated by ENG-455 rather than by this file.

    Delete this case when the key is retired; until then a change that stops accepting it
    stops every tablet in the field, and this is what says so out loud.
    """
    served = await open_a_session(client, {ROOM_KEY_HEADER: KEY})

    assert served.status_code == 200, served.text


async def test_a_request_with_neither_credential_nor_key_is_refused(client):
    served = await open_a_session(client, {})

    assert served.status_code == 401


# Behaviour 4 — a credential names one device, and through it one project.


async def test_one_devices_credential_never_resolves_another_devices_project(client, db_session):
    """Two claimed devices exist; the credential of one resolves that one's project.

    The second device is not decoration. With only one device on the table, a resolver that
    answered with "the project of whichever device is first" would pass — the case has to be
    able to pick the wrong one to mean anything.
    """
    mine = await a_claimed_device(db_session)
    theirs = await a_claimed_device(db_session, email="other@example.com")
    assert mine.project.id != theirs.project.id, "o cenario nao provou nada: um projeto so"

    opened = await open_a_session(client, {DEVICE_CREDENTIAL_HEADER: theirs.credential})

    session = await room_sessions.get_session(db_session, opened.json()["session_id"])
    assert session.project_id == theirs.project.id
