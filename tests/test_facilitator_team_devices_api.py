"""ENG-444 — a team's devices: list them, say who uses them, take one out of service.

Two of these carry the slice.

Behaviour 2 repeats ENG-443's non-enumeration rule on a different route. Closing that
hole at the claim and leaving it open at the list would be no better than not closing it,
so the refusal for a team the caller does not facilitate is asserted equal to the refusal
for a team that does not exist.

Behaviour 4 asserts revocation from the device's side. Reading the row back and finding
it tidy proves nothing — a revocation that updates the record and keeps authenticating is
the failure worth catching, and only the device's own next request can see it.
"""

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ProjectRole
from app.services.device import create_device
from tests.baker import (
    grant_facilitator_app_role,
    make_language,
    make_project,
    make_project_user_access,
    make_user,
)

CLAIM_URL = "/api/facilitator/devices/claim"
DEVICE_SELF_URL = "/api/devices/me"
DEVICE_CREDENTIAL_HEADER = "X-Device-Credential"


def team_devices_url(team_id: str) -> str:
    return f"/api/facilitator/teams/{team_id}/devices"


def device_url(device_id: str) -> str:
    return f"/api/facilitator/devices/{device_id}"


@pytest.fixture()
async def client(db_session: AsyncSession):
    from fastapi import FastAPI

    from app.api.devices import devices_router
    from app.api.facilitator.devices import facilitator_devices_router
    from app.api.facilitator.teams import facilitator_teams_router
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    test_app = FastAPI()
    test_app.include_router(facilitator_devices_router, prefix="/api/facilitator/devices")
    test_app.include_router(facilitator_teams_router, prefix="/api/facilitator/teams")
    test_app.include_router(devices_router, prefix="/api/devices")
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def auth_header(db: AsyncSession, user) -> dict[str, str]:
    from app.services.auth.issue_tokens import issue_tokens

    access, _refresh = await issue_tokens(db, user)
    return {"Authorization": f"Bearer {access}"}


async def a_facilitator(db: AsyncSession, *, email="facilitator@example.com"):
    user = await make_user(db, email=email)
    language = await make_language(db, name=f"Lang {email}", code=email[:3])
    project = await make_project(db, language.id, name=f"Team {email}")
    await make_project_user_access(db, project.id, user.id, role=ProjectRole.FACILITATOR)
    await grant_facilitator_app_role(db, user.id)
    return user, project, await auth_header(db, user)


async def a_linked_device(client, db, headers, project, *, label=None):
    """A device claimed into ``project``. Returns (device_id, credential)."""
    minted = await create_device(db)
    body = {"code": minted.claim_code, "project_id": project.id}
    if label is not None:
        body["label"] = label
    answer = (await client.post(CLAIM_URL, json=body, headers=headers)).json()
    return answer["device_id"], answer["credential"]


# Behaviour 1 — the list shows a team's devices and nothing else.


async def test_the_list_returns_the_devices_of_the_team_it_was_asked_for(client, db_session):
    _user, project, headers = await a_facilitator(db_session)
    first, _c1 = await a_linked_device(client, db_session, headers, project, label="Ana's")
    second, _c2 = await a_linked_device(client, db_session, headers, project)

    listed = await client.get(team_devices_url(project.id), headers=headers)

    assert listed.status_code == 200
    assert {row["device_id"] for row in listed.json()} == {first, second}


async def test_the_list_does_not_show_another_teams_devices(client, db_session):
    _user, project, headers = await a_facilitator(db_session)
    mine, _c = await a_linked_device(client, db_session, headers, project)
    _other, other_project, other_headers = await a_facilitator(
        db_session, email="other@example.com"
    )
    theirs, _c2 = await a_linked_device(client, db_session, other_headers, other_project)

    listed = await client.get(team_devices_url(project.id), headers=headers)

    device_ids = {row["device_id"] for row in listed.json()}
    assert mine in device_ids
    assert theirs not in device_ids


async def test_the_list_carries_who_uses_it_and_when_it_was_linked(client, db_session):
    _user, project, headers = await a_facilitator(db_session)
    await a_linked_device(client, db_session, headers, project, label="second row, cracked")

    row = (await client.get(team_devices_url(project.id), headers=headers)).json()[0]

    assert row["label"] == "second row, cracked"
    assert row["linked_at"]


async def test_a_team_with_no_devices_answers_with_an_empty_list(client, db_session):
    _user, project, headers = await a_facilitator(db_session)

    listed = await client.get(team_devices_url(project.id), headers=headers)

    assert listed.status_code == 200
    assert listed.json() == []


# Behaviour 2 — listing a team you do not facilitate tells you nothing.


async def test_listing_a_team_you_do_not_facilitate_answers_like_a_team_that_does_not_exist(
    client, db_session
):
    _user, _own, headers = await a_facilitator(db_session)
    _stranger, someone_elses, _their_headers = await a_facilitator(
        db_session, email="stranger@example.com"
    )

    not_yours = await client.get(team_devices_url(someone_elses.id), headers=headers)
    no_such_team = await client.get(
        team_devices_url("00000000-0000-0000-0000-000000000000"), headers=headers
    )

    assert not_yours.status_code == no_such_team.status_code
    assert not_yours.json() == no_such_team.json()
    assert not_yours.content == no_such_team.content


async def test_editing_a_device_of_another_team_answers_like_a_device_that_does_not_exist(
    client, db_session
):
    _user, _own, headers = await a_facilitator(db_session)
    _stranger, someone_elses, their_headers = await a_facilitator(
        db_session, email="stranger@example.com"
    )
    theirs, _c = await a_linked_device(client, db_session, their_headers, someone_elses)

    not_yours = await client.patch(device_url(theirs), json={"label": "mine now"}, headers=headers)
    no_such_device = await client.patch(
        device_url("00000000-0000-0000-0000-000000000000"),
        json={"label": "mine now"},
        headers=headers,
    )

    assert not_yours.status_code == no_such_device.status_code
    assert not_yours.content == no_such_device.content


async def test_unlinking_a_device_of_another_team_answers_like_a_device_that_does_not_exist(
    client, db_session
):
    _user, _own, headers = await a_facilitator(db_session)
    _stranger, someone_elses, their_headers = await a_facilitator(
        db_session, email="stranger@example.com"
    )
    theirs, credential = await a_linked_device(client, db_session, their_headers, someone_elses)

    not_yours = await client.delete(device_url(theirs), headers=headers)
    no_such_device = await client.delete(
        device_url("00000000-0000-0000-0000-000000000000"), headers=headers
    )

    assert not_yours.status_code == no_such_device.status_code
    assert not_yours.content == no_such_device.content

    still_working = await client.get(
        DEVICE_SELF_URL, headers={DEVICE_CREDENTIAL_HEADER: credential}
    )
    assert still_working.status_code == 200


async def test_an_unauthenticated_caller_cannot_list_a_teams_devices(client, db_session):
    _user, project, _headers = await a_facilitator(db_session)

    listed = await client.get(team_devices_url(project.id))

    assert listed.status_code == 401


# Behaviour 3 — the label is a human note, not a credential.


async def test_editing_the_label_stores_free_text_verbatim(client, db_session):
    _user, project, headers = await a_facilitator(db_session)
    device_id, _c = await a_linked_device(client, db_session, headers, project)
    written_by_a_human = "  Ana's tablet (cracked) — 2nd row / turno da tarde  "

    edited = await client.patch(
        device_url(device_id), json={"label": written_by_a_human}, headers=headers
    )

    assert edited.status_code == 200
    row = (await client.get(team_devices_url(project.id), headers=headers)).json()[0]
    assert row["label"] == written_by_a_human


async def test_editing_the_label_accepts_empty(client, db_session):
    _user, project, headers = await a_facilitator(db_session)
    device_id, _c = await a_linked_device(client, db_session, headers, project, label="was set")

    edited = await client.patch(device_url(device_id), json={"label": ""}, headers=headers)

    assert edited.status_code == 200
    row = (await client.get(team_devices_url(project.id), headers=headers)).json()[0]
    assert row["label"] == ""


async def test_the_label_grants_nothing_to_the_device_that_carries_it(client, db_session):
    _user, project, headers = await a_facilitator(db_session)
    _labelled, labelled_credential = await a_linked_device(
        client, db_session, headers, project, label="important sounding"
    )
    _bare, bare_credential = await a_linked_device(client, db_session, headers, project)

    labelled_sees = await client.get(
        DEVICE_SELF_URL, headers={DEVICE_CREDENTIAL_HEADER: labelled_credential}
    )
    bare_sees = await client.get(
        DEVICE_SELF_URL, headers={DEVICE_CREDENTIAL_HEADER: bare_credential}
    )

    assert labelled_sees.status_code == bare_sees.status_code == 200
    assert labelled_sees.json()["project_id"] == bare_sees.json()["project_id"] == project.id


# Behaviour 4 — unlinking revokes, and the device finds out by being refused.


async def test_unlinking_a_device_makes_its_next_request_be_refused(client, db_session):
    """403, not the 401 this asserted when it was written.

    ENG-448 gives revocation a status of its own, so the tablet can tell "you were
    unlinked" from "that string is not a credential" and forget what it holds in the first
    case only. The refusal is the same refusal; what changed is that it says which one it
    is. The case below reads the same way.
    """
    _user, project, headers = await a_facilitator(db_session)
    device_id, credential = await a_linked_device(client, db_session, headers, project)
    assert (
        await client.get(DEVICE_SELF_URL, headers={DEVICE_CREDENTIAL_HEADER: credential})
    ).status_code == 200

    unlinked = await client.delete(device_url(device_id), headers=headers)

    assert unlinked.status_code in (200, 204)
    refused = await client.get(DEVICE_SELF_URL, headers={DEVICE_CREDENTIAL_HEADER: credential})
    assert refused.status_code == 403


async def test_an_unlinked_devices_credential_cannot_be_brought_back(client, db_session):
    _user, project, headers = await a_facilitator(db_session)
    device_id, credential = await a_linked_device(client, db_session, headers, project)
    await client.delete(device_url(device_id), headers=headers)

    # Nothing the facilitator can do short of a fresh claim puts the device back: editing
    # it is the only other write this slice offers, and it must not resurrect anything.
    await client.patch(device_url(device_id), json={"label": "back please"}, headers=headers)

    refused = await client.get(DEVICE_SELF_URL, headers={DEVICE_CREDENTIAL_HEADER: credential})
    assert refused.status_code == 403


async def test_unlinking_a_device_that_was_never_claimed_is_refused_like_one_that_is_absent(
    client, db_session
):
    _user, _project, headers = await a_facilitator(db_session)
    unclaimed = await create_device(db_session)

    unlinked = await client.delete(device_url(unclaimed.device.id), headers=headers)

    # It belongs to no team, so the caller may not touch it, and learns nothing about it.
    no_such_device = await client.delete(
        device_url("00000000-0000-0000-0000-000000000000"), headers=headers
    )
    assert unlinked.status_code == no_such_device.status_code
    assert unlinked.content == no_such_device.content


# Behaviour 5 — one count, one source.


async def test_an_unlinked_device_leaves_the_list(client, db_session):
    _user, project, headers = await a_facilitator(db_session)
    staying, _c1 = await a_linked_device(client, db_session, headers, project)
    going, _c2 = await a_linked_device(client, db_session, headers, project)

    await client.delete(device_url(going), headers=headers)

    device_ids = {
        row["device_id"]
        for row in (await client.get(team_devices_url(project.id), headers=headers)).json()
    }
    assert device_ids == {staying}


async def test_last_activity_is_null_until_the_device_asks_the_api_something(client, db_session):
    """The column has to be written, not merely present in the answer.

    Asserting the key exists passes just as well when nothing ever sets it, which would
    leave the Desk showing an always-empty column and this test agreeing.
    """
    _user, project, headers = await a_facilitator(db_session)
    await a_linked_device(client, db_session, headers, project)

    before = (await client.get(team_devices_url(project.id), headers=headers)).json()[0]

    assert before["last_seen_at"] is None


async def test_last_activity_is_set_once_the_device_reads_its_own_team(client, db_session):
    _user, project, headers = await a_facilitator(db_session)
    _device_id, credential = await a_linked_device(client, db_session, headers, project)

    await client.get(DEVICE_SELF_URL, headers={DEVICE_CREDENTIAL_HEADER: credential})

    after = (await client.get(team_devices_url(project.id), headers=headers)).json()[0]
    assert after["last_seen_at"] is not None
