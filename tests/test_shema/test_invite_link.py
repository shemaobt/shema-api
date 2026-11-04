"""The invitation's two doors under ``/api/shema`` — OBT-683, the module's third deliberate hole.

The PME's ``/convite`` reads an invitation before the person has an account and accepts it once
they have one. Both calls moved here from the form's prefix with the contract unchanged: the
same snake_case shapes, the same refusals, the same two services behind them. What the page
relies on is what each case below holds — the lookup needs no ``Authorization``, the acceptance
needs a sign-in and nothing else, and until the form's two routes leave, both prefixes answer
one invitation alike.

Who may *send* an invitation, and what accepting one writes — the role, the regions, a team's
membership — is ``test_admin_invites.py`` and ``test_pending_projects.py``, which accept on these
doors too.
"""

from __future__ import annotations

import httpx
import pytest
from httpx import ASGITransport

from app.api.shema._deps import APP_KEY
from app.main import create_app
from tests.shema_admin_harness import INVITES, give_urls, make_admin, surface_client
from tests.test_shema.conftest import SESSION

#: What ``/convite`` reads off the lookup, in the form's spelling — the contract the move kept.
LOOKUP_KEYS = {
    "status",
    "email",
    "app_name",
    "role_key",
    "role_label",
    "account_exists",
    "region_keys",
}

#: The form's two doors, which answer until the PR that removes them; only the transition's own
#: case below calls them.
FORM_INVITES = "/api/resource-requests/access/invites"

JOINER = "joiner@shema.example"


async def _invite(client: httpx.AsyncClient, headers: dict[str, str]) -> str:
    """An ``obtLab`` invitation over Asia, sent by the Admin; answers the link's token."""
    sent = await client.post(
        INVITES,
        json={"email": JOINER, "appKey": APP_KEY, "roleKey": "obtLab", "regionKeys": ["asia"]},
        headers=headers,
    )
    assert sent.status_code == 201, sent.text
    return sent.json()["inviteUrl"].split("token=")[1]


async def _signup(client: httpx.AsyncClient) -> dict[str, str]:
    res = await client.post(
        "/api/auth/signup",
        json={"email": JOINER, "password": "a-long-password", "display_name": "Joiner"},
    )
    assert res.status_code == 201, res.text
    return {"Authorization": f"Bearer {res.json()['tokens']['access_token']}"}


async def test_the_link_is_read_with_no_authorization_and_answers_the_shape_convite_reads(
    db_session, shema_app, form_app
) -> None:
    """No bearer at all — the person has no account yet — and the form's seven keys, as written."""
    await give_urls(db_session, shema_app, form_app)
    _admin, headers = await make_admin(db_session, shema_app, form_app)

    async with surface_client(db_session) as client:
        token = await _invite(client, headers)
        res = await client.get(f"{INVITES}/{token}")

    assert res.status_code == 200, res.text
    body = res.json()
    assert set(body) == LOOKUP_KEYS
    assert (body["status"], body["email"], body["role_key"]) == ("pending", JOINER, "obtLab")
    assert (body["account_exists"], body["region_keys"]) == (False, ["asia"])
    assert token not in res.text


async def test_accepting_needs_a_sign_in_and_nothing_else(db_session, shema_app, form_app) -> None:
    """Without a bearer the acceptance is a 401 and the link stays live; an account that holds
    nothing anywhere — the door refuses its session — accepts, and holds the role afterwards."""
    await give_urls(db_session, shema_app, form_app)
    admin, headers = await make_admin(db_session, shema_app, form_app)

    async with surface_client(db_session) as client:
        token = await _invite(client, headers)
        anonymous = await client.post(f"{INVITES}/{token}/accept")
        still = await client.get(f"{INVITES}/{token}")
        joiner = await _signup(client)
        before = await client.get(SESSION, headers=joiner)
        accepted = await client.post(f"{INVITES}/{token}/accept", headers=joiner)
        after = await client.get(SESSION, headers=joiner)

    assert anonymous.status_code == 401
    assert still.json()["status"] == "pending"
    assert before.status_code == 403
    assert accepted.status_code == 200, accepted.text
    assert (accepted.json()["role_key"], accepted.json()["granted_by"]) == ("obtLab", admin.id)
    assert (after.json()["roles"], after.json()["regionScope"]) == (["obtLab"], ["asia"])


@pytest.fixture()
async def server(db_session):
    """The application ``app/main.py`` builds, where both prefixes are mounted."""
    from app.core.database import get_db

    app = create_app()

    async def _get_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_db
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_both_prefixes_answer_one_invitation_alike_until_the_form_s_leave(
    db_session, server, shema_app, form_app
) -> None:
    """**The transition, and it leaves with the form's routes**: the PR that removes them deletes
    this case and nothing else here. One invitation, read on both before and after it is spent
    through the module's door; spent again on each, the same 409; an unknown link, the same 404.
    """
    await give_urls(db_session, shema_app, form_app)
    _admin, headers = await make_admin(db_session, shema_app, form_app)
    token = await _invite(server, headers)

    pending = [(await server.get(f"{prefix}/{token}")).json() for prefix in (INVITES, FORM_INVITES)]
    joiner = await _signup(server)
    accepted = await server.post(f"{INVITES}/{token}/accept", headers=joiner)
    used = [(await server.get(f"{prefix}/{token}")).json() for prefix in (INVITES, FORM_INVITES)]
    again = [
        await server.post(f"{prefix}/{token}/accept", headers=joiner)
        for prefix in (INVITES, FORM_INVITES)
    ]
    unknown = [await server.get(f"{prefix}/never-issued") for prefix in (INVITES, FORM_INVITES)]

    assert pending[0] == pending[1] and pending[0]["status"] == "pending"
    assert accepted.status_code == 200, accepted.text
    assert used[0] == used[1] and used[0]["status"] == "used"
    assert [res.status_code for res in again] == [409, 409]
    assert again[0].json() == again[1].json()
    assert again[0].json()["detail"] == "This invitation has already been used."
    assert [res.status_code for res in unknown] == [404, 404]
    assert unknown[0].json() == unknown[1].json()
