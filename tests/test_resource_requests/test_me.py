"""``GET /me`` — who the account is in the form, the team included (FE-52, OBT-538).

``GET /api/auth/my-roles`` answers grants, and since BE-19 the team holds none: every team
account read as *without a role* there, and the form refused it at login and signed it out at
every boot. These tests hold the form's own answer to that question.
"""

from __future__ import annotations

from datetime import UTC, datetime

from tests.baker import make_user
from tests.test_resource_requests.conftest import auth_header, grant, make_membership

ME = "/api/resource-requests/me"


async def test_a_member_with_no_grant_is_equipe_with_their_projects(
    db_session, client, rrf_app
) -> None:
    user = await make_user(db_session, email="membro@me.test")
    await make_membership(db_session, user, "kadiweu")
    await make_membership(db_session, user, "fataluku")

    res = await client.get(ME, headers=await auth_header(db_session, user))

    assert res.status_code == 200, res.text
    assert res.json() == {"roles": ["equipe"], "projects": ["fataluku", "kadiweu"]}


async def test_a_grant_answers_as_itself(db_session, client, rrf_app) -> None:
    user = await make_user(db_session, email="mesa@me.test")
    await grant(db_session, user, rrf_app, "mesa")

    res = await client.get(ME, headers=await auth_header(db_session, user))

    assert res.json() == {"roles": ["mesa"], "projects": []}


async def test_a_grant_and_a_membership_add_up(db_session, client, rrf_app) -> None:
    """The floor accumulates (GATE-02 D1), the rule the form's ``roleFromClaims`` reads."""
    user = await make_user(db_session, email="gestor@me.test")
    await grant(db_session, user, rrf_app, "gestor")
    await make_membership(db_session, user, "kadiweu")

    res = await client.get(ME, headers=await auth_header(db_session, user))

    assert res.json() == {"roles": ["equipe", "gestor"], "projects": ["kadiweu"]}


async def test_a_removed_member_is_no_longer_equipe(db_session, client, rrf_app) -> None:
    user = await make_user(db_session, email="saiu@me.test")
    stay = await make_membership(db_session, user, "kadiweu")
    stay.removed_at = datetime.now(UTC)
    await db_session.commit()

    res = await client.get(ME, headers=await auth_header(db_session, user))

    assert res.json() == {"roles": [], "projects": []}


async def test_an_account_with_nothing_is_told_so_not_refused(db_session, client, rrf_app) -> None:
    """Empty lists and not a 403: the form has a sentence for *without a role in this app*,
    and it needs the answer to say it."""
    user = await make_user(db_session, email="ninguem@me.test")

    res = await client.get(ME, headers=await auth_header(db_session, user))

    assert res.status_code == 200, res.text
    assert res.json() == {"roles": [], "projects": []}


async def test_no_session_is_refused(client, rrf_app) -> None:
    assert (await client.get(ME)).status_code == 401
