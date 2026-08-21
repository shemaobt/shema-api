"""ENG-439 — facilitating a team is narrower than having access to it.

Until this slice, every facilitator route asked ``can_access_project``, which answers yes
to a project member, yes to a project manager, and yes to anyone who reaches the project
through an organization. The Desk means something narrower: a facilitator is a
``project_user_access`` row whose role says so.

Behaviour 2 is the driver and it fails against the code as it stood — all three of those
callers could claim a device into a team, list its devices, rename them and unlink them.
"""

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ProjectRole
from app.core.exceptions import ValidationError
from app.services.device import create_device
from app.services.project.grant_user_access import grant_user_access
from app.services.project.list_facilitated_project_ids import list_facilitated_project_ids
from app.services.project.update_user_access_role import update_user_access_role
from tests.baker import (
    grant_facilitator_app_role,
    make_language,
    make_organization,
    make_organization_member,
    make_project,
    make_project_organization_access,
    make_project_user_access,
    make_user,
)

CLAIM_URL = "/api/facilitator/devices/claim"


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


async def a_team(db: AsyncSession, *, name="Team"):
    language = await make_language(db, name=f"Lang {name}", code=name[:3].lower())
    return await make_project(db, language.id, name=name)


async def a_user_holding(db: AsyncSession, project, role, *, email):
    """A user linked to ``project`` with ``role``. Returns (user, auth headers)."""
    user = await make_user(db, email=email)
    await make_project_user_access(db, project.id, user.id, role=role)
    await grant_facilitator_app_role(db, user.id)
    return user, await auth_header(db, user)


async def a_user_via_organization(db: AsyncSession, project, *, email):
    """A user who reaches ``project`` only through organization membership."""
    user = await make_user(db, email=email)
    org = await make_organization(db, name=f"Org {email}", slug=email.split("@")[0])
    await make_organization_member(db, user.id, org.id)
    await make_project_organization_access(db, project.id, org.id)
    await grant_facilitator_app_role(db, user.id)
    return user, await auth_header(db, user)


async def a_device_linked_by_a_facilitator(client, db, team, *, email):
    """A device already claimed into ``team``, so rename and unlink have a real target.

    Without this the device has no project, every device route refuses it before it ever
    reaches the authorisation check, and a test that meant to exercise that check would
    be passing on the wrong refusal.
    """
    _fac, fac_headers = await a_user_holding(db, team, ProjectRole.FACILITATOR, email=email)
    minted = await create_device(db)
    answer = await client.post(
        CLAIM_URL,
        json={"code": minted.claim_code, "project_id": team.id},
        headers=fac_headers,
    )
    assert answer.status_code == 200, answer.text
    return answer.json()["device_id"]


async def every_facilitator_route(client, headers, *, team, device_id, code):
    """Every write and read this stack exposes, as (name, response)."""
    return [
        (
            "claim",
            await client.post(
                CLAIM_URL, json={"code": code, "project_id": team.id}, headers=headers
            ),
        ),
        ("list", await client.get(team_devices_url(team.id), headers=headers)),
        (
            "rename",
            await client.patch(device_url(device_id), json={"label": "mine now"}, headers=headers),
        ),
        ("unlink", await client.delete(device_url(device_id), headers=headers)),
    ]


# Behaviour 1 — a facilitator sees exactly their teams.


async def test_a_facilitator_reaches_the_teams_they_facilitate(client, db_session):
    first = await a_team(db_session, name="First")
    second = await a_team(db_session, name="Second")
    user = await make_user(db_session, email="fac@example.com")
    await make_project_user_access(db_session, first.id, user.id, role=ProjectRole.FACILITATOR)
    await make_project_user_access(db_session, second.id, user.id, role=ProjectRole.FACILITATOR)
    await grant_facilitator_app_role(db_session, user.id)
    headers = await auth_header(db_session, user)

    assert (await client.get(team_devices_url(first.id), headers=headers)).status_code == 200
    assert (await client.get(team_devices_url(second.id), headers=headers)).status_code == 200


async def test_a_facilitator_does_not_reach_a_team_they_are_not_linked_to(client, db_session):
    theirs = await a_team(db_session, name="Theirs")
    not_theirs = await a_team(db_session, name="Stranger")
    _user, headers = await a_user_holding(
        db_session, theirs, ProjectRole.FACILITATOR, email="fac@example.com"
    )

    assert (await client.get(team_devices_url(not_theirs.id), headers=headers)).status_code == 404


async def test_facilitating_one_team_and_belonging_to_another_reaches_only_the_first(
    client, db_session
):
    facilitated = await a_team(db_session, name="Facilitated")
    merely_member = await a_team(db_session, name="Member")
    user = await make_user(db_session, email="both@example.com")
    await make_project_user_access(
        db_session, facilitated.id, user.id, role=ProjectRole.FACILITATOR
    )
    await make_project_user_access(db_session, merely_member.id, user.id, role=ProjectRole.MEMBER)
    await grant_facilitator_app_role(db_session, user.id)
    headers = await auth_header(db_session, user)

    assert (await client.get(team_devices_url(facilitated.id), headers=headers)).status_code == 200
    assert (
        await client.get(team_devices_url(merely_member.id), headers=headers)
    ).status_code == 404


# Behaviour 2 — access is not the same as facilitating.
#
# The driver. Every one of these callers could do all four of these things before this
# slice, because can_access_project answers yes to each of them.


@pytest.mark.parametrize("role", [ProjectRole.MEMBER, ProjectRole.MANAGER])
async def test_a_project_role_that_is_not_facilitator_is_refused_everywhere(
    client, db_session, role
):
    team = await a_team(db_session)
    linked = await a_device_linked_by_a_facilitator(
        client, db_session, team, email=f"owner-{role}@example.com"
    )
    _user, headers = await a_user_holding(db_session, team, role, email=f"{role}@example.com")
    unclaimed = await create_device(db_session)

    for name, response in await every_facilitator_route(
        client, headers, team=team, device_id=linked, code=unclaimed.claim_code
    ):
        assert response.status_code != 200, f"{role} was allowed to {name}"
        assert response.status_code != 204, f"{role} was allowed to {name}"


async def test_reaching_a_project_only_through_an_organization_is_refused_everywhere(
    client, db_session
):
    team = await a_team(db_session)
    linked = await a_device_linked_by_a_facilitator(
        client, db_session, team, email="owner-org@example.com"
    )
    _user, headers = await a_user_via_organization(db_session, team, email="org@example.com")
    unclaimed = await create_device(db_session)

    for name, response in await every_facilitator_route(
        client, headers, team=team, device_id=linked, code=unclaimed.claim_code
    ):
        assert response.status_code != 200, f"organization access was allowed to {name}"
        assert response.status_code != 204, f"organization access was allowed to {name}"


async def test_a_member_cannot_claim_a_device_into_the_team(client, db_session):
    team = await a_team(db_session)
    _user, headers = await a_user_holding(
        db_session, team, ProjectRole.MEMBER, email="member@example.com"
    )
    device = await create_device(db_session)

    claimed = await client.post(
        CLAIM_URL, json={"code": device.claim_code, "project_id": team.id}, headers=headers
    )

    assert claimed.status_code == 400
    # And the code is still there to be spent by someone who may.
    _fac, fac_headers = await a_user_holding(
        db_session, team, ProjectRole.FACILITATOR, email="fac@example.com"
    )
    assert (
        await client.post(
            CLAIM_URL, json={"code": device.claim_code, "project_id": team.id}, headers=fac_headers
        )
    ).status_code == 200


# Behaviour 3 — a facilitator with no teams is a valid person.


async def test_a_facilitator_with_no_teams_facilitates_an_empty_set(db_session):
    user = await make_user(db_session, email="new@example.com")

    assert await list_facilitated_project_ids(db_session, user) == set()


async def test_a_facilitator_with_no_teams_is_refused_like_anyone_else_not_a_special_error(
    client, db_session
):
    team = await a_team(db_session)
    user = await make_user(db_session, email="new@example.com")
    await grant_facilitator_app_role(db_session, user.id)
    headers = await auth_header(db_session, user)

    unlinked_caller = await client.get(team_devices_url(team.id), headers=headers)
    no_such_team = await client.get(
        team_devices_url("00000000-0000-0000-0000-000000000000"), headers=headers
    )

    assert unlinked_caller.status_code == 404
    assert unlinked_caller.content == no_such_team.content


# Behaviour 4 — a platform admin is not scoped to nothing.


async def test_a_platform_admin_facilitates_every_team(client, db_session):
    first = await a_team(db_session, name="First")
    second = await a_team(db_session, name="Second")
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    headers = await auth_header(db_session, admin)

    assert await list_facilitated_project_ids(db_session, admin) == {first.id, second.id}
    assert (await client.get(team_devices_url(first.id), headers=headers)).status_code == 200
    assert (await client.get(team_devices_url(second.id), headers=headers)).status_code == 200


# Behaviour 5 — refusal is one shape, everywhere, and it does not enumerate.


async def test_every_team_route_refuses_a_team_that_is_not_yours_exactly_as_one_that_is_absent(
    client, db_session
):
    someone_elses = await a_team(db_session, name="Stranger")
    _user, headers = await a_user_holding(
        db_session,
        await a_team(db_session, name="Mine"),
        ProjectRole.FACILITATOR,
        email="fac@example.com",
    )
    absent = "00000000-0000-0000-0000-000000000000"

    not_yours = await client.get(team_devices_url(someone_elses.id), headers=headers)
    no_such = await client.get(team_devices_url(absent), headers=headers)

    assert not_yours.status_code == no_such.status_code == 404
    assert not_yours.content == no_such.content


async def test_the_claim_route_keeps_its_own_refusal_shape(client, db_session):
    """ENG-443's property survives the retrofit.

    The claim refusal stays a 400 that is byte-identical to an unknown code, rather than
    becoming the 404 the team routes use. A 404 here would tell the facilitator that the
    team was the problem and not the code, which is precisely the enumeration ENG-443
    closed.
    """
    someone_elses = await a_team(db_session, name="Stranger")
    mine = await a_team(db_session, name="Mine")
    _user, headers = await a_user_holding(
        db_session, mine, ProjectRole.FACILITATOR, email="fac@example.com"
    )
    device = await create_device(db_session)

    not_yours = await client.post(
        CLAIM_URL,
        json={"code": device.claim_code, "project_id": someone_elses.id},
        headers=headers,
    )
    unknown_code = await client.post(
        CLAIM_URL, json={"code": "AAA-AAAA", "project_id": mine.id}, headers=headers
    )

    assert not_yours.status_code == unknown_code.status_code == 400
    assert not_yours.content == unknown_code.content


# Behaviour 6 — the role column refuses nonsense.


async def test_granting_an_undocumented_role_is_rejected(db_session):
    team = await a_team(db_session)
    user = await make_user(db_session, email="typo@example.com")

    with pytest.raises(ValidationError):
        await grant_user_access(db_session, team.id, user.id, role="facilitatr")


async def test_updating_to_an_undocumented_role_is_rejected(db_session):
    team = await a_team(db_session)
    user = await make_user(db_session, email="typo@example.com")
    await grant_user_access(db_session, team.id, user.id, role=ProjectRole.MEMBER)

    with pytest.raises(ValidationError):
        await update_user_access_role(db_session, team.id, user.id, role="Facilitator")


async def test_the_documented_roles_are_accepted(db_session):
    team = await a_team(db_session)
    for index, role in enumerate(ProjectRole):
        user = await make_user(db_session, email=f"role{index}@example.com")
        granted = await grant_user_access(db_session, team.id, user.id, role=role)
        assert granted.role == role


async def test_a_role_the_column_already_holds_still_denies_rather_than_grants(client, db_session):
    """Enforcement is at the write path, so a row written another way can hold anything.

    What matters is which way that fails. The scoping asks for exactly the facilitator
    role, so an unrecognised value denies — a row that predates this slice, or one written
    by direct SQL, cannot grant more than it should.
    """
    team = await a_team(db_session)
    for index, stored in enumerate(["something_older", "Facilitator", " facilitator ", ""]):
        user = await make_user(db_session, email=f"legacy{index}@example.com")
        await make_project_user_access(db_session, team.id, user.id, role=stored)
        await grant_facilitator_app_role(db_session, user.id)
        headers = await auth_header(db_session, user)

        answer = await client.get(team_devices_url(team.id), headers=headers)
        assert answer.status_code == 404, f"{stored!r} was treated as the facilitator role"
