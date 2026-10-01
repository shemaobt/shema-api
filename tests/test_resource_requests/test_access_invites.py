"""The two invite doors the PME's ``/convite`` page still calls — FE-56 (OBT-549).

The form's own access doors — the overview, naming, revoking, issuing and withdrawing an
invite — left with its access screen: roles are granted in the PME now, by the Admin alone
(OBT-522), and issuing, withdrawing and the duplicate and self-invite refusals are covered
where they live, in ``tests/test_shema/test_admin_invites.py``. What stays here is what an
anonymous link-holder is answered and what accepting does, with the invite written straight
through ``invite_store`` — the same store the PME's door writes through.

Addresses are ``@rrf.example`` and never ``@rrf.test``: ``email-validator`` refuses the reserved
``.test`` TLD outright.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.db.models.auth import AccessInvite
from app.services.resource_request_access.invite_store import issue_invite
from tests.baker import make_user
from tests.test_resource_requests.conftest import auth_header, grant

ACCESS = "/api/resource-requests/access"


async def _invite(
    db_session, inviter, email: str = "stranger@rrf.example", role_key: str = "equipe"
) -> str:
    issued = await issue_invite(db_session, inviter, "resource-request-form", email, role_key)
    return issued.raw_token


async def _admin(db_session, email: str = "padmin@rrf.example"):
    return await make_user(db_session, email=email, is_platform_admin=True)


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", ""),
        ("post", "/grants"),
        ("post", "/grants/revoke"),
        ("post", "/invites"),
        ("post", "/invites/revoke"),
    ],
)
async def test_the_forms_own_access_doors_are_gone(
    db_session, client, rrf_app, method: str, path: str
) -> None:
    """The five doors FE-30 used are gone, whoever asks.

    Four answer 404. ``POST /invites/revoke`` answers **405**: its path now matches the public
    lookup ``GET /invites/{token}`` with ``revoke`` as the token, and only the method is
    refused — the door is gone all the same, and nothing behind it runs.
    """
    headers = await auth_header(db_session, await _admin(db_session))

    res = await client.request(method.upper(), f"{ACCESS}{path}", json={}, headers=headers)

    expected = 405 if path == "/invites/revoke" else 404
    assert res.status_code == expected, res.text


async def test_the_public_lookup_sends_a_stranger_to_signup(db_session, client, rrf_app) -> None:
    """No auth header anywhere in this test — the endpoint's whole point."""
    token = await _invite(db_session, await _admin(db_session))

    res = await client.get(f"{ACCESS}/invites/{token}")

    assert res.status_code == 200
    description = res.json()
    assert description["status"] == "pending"
    assert description["email"] == "stranger@rrf.example"
    assert description["account_exists"] is False
    assert description["role_key"] == "equipe"
    assert description["app_name"] == "Resource Request Form"


async def test_the_public_lookup_recognises_an_existing_account(
    db_session, client, rrf_app
) -> None:
    await make_user(db_session, email="known@rrf.example")
    token = await _invite(db_session, await _admin(db_session), email="known@rrf.example")

    res = await client.get(f"{ACCESS}/invites/{token}")

    assert res.json()["account_exists"] is True


async def test_an_unknown_token_is_a_404(client, rrf_app) -> None:
    res = await client.get(f"{ACCESS}/invites/deadbeef")
    assert res.status_code == 404


async def test_accepting_grants_the_role_in_the_inviters_name_and_spends_the_invite(
    db_session, client, rrf_app
) -> None:
    inviter = await _admin(db_session)
    token = await _invite(db_session, inviter, role_key="mesa")
    joiner = await make_user(db_session, email="stranger@rrf.example")
    joiner_headers = await auth_header(db_session, joiner)

    accepted = await client.post(f"{ACCESS}/invites/{token}/accept", headers=joiner_headers)
    again = await client.post(f"{ACCESS}/invites/{token}/accept", headers=joiner_headers)

    assert accepted.status_code == 200
    grant_body = accepted.json()
    assert grant_body["user_id"] == joiner.id
    assert grant_body["role_key"] == "mesa"
    assert grant_body["granted_by"] == inviter.id
    assert again.status_code == 409

    lookup = await client.get(f"{ACCESS}/invites/{token}")
    assert lookup.json()["status"] == "used"


async def test_a_link_in_the_wrong_hands_is_refused(db_session, client, rrf_app) -> None:
    token = await _invite(db_session, await _admin(db_session))
    other = await make_user(db_session, email="someone-else@rrf.example")

    res = await client.post(
        f"{ACCESS}/invites/{token}/accept", headers=await auth_header(db_session, other)
    )

    assert res.status_code == 403


async def test_an_expired_invite_neither_reads_pending_nor_accepts(
    db_session, client, rrf_app
) -> None:
    token = await _invite(db_session, await _admin(db_session))
    row = (await db_session.execute(select(AccessInvite))).scalar_one()
    row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    await db_session.commit()
    joiner = await make_user(db_session, email="stranger@rrf.example")

    lookup = await client.get(f"{ACCESS}/invites/{token}")
    accept = await client.post(
        f"{ACCESS}/invites/{token}/accept", headers=await auth_header(db_session, joiner)
    )

    assert lookup.json()["status"] == "expired"
    assert accept.status_code == 409


async def test_exclusivity_holds_at_acceptance_time_too(db_session, client, rrf_app) -> None:
    """The holder's roles may change between the letter and the click."""
    token = await _invite(db_session, await _admin(db_session), role_key="mesa")
    joiner = await make_user(db_session, email="stranger@rrf.example")
    await grant(db_session, joiner, rrf_app, "gestor")

    res = await client.post(
        f"{ACCESS}/invites/{token}/accept", headers=await auth_header(db_session, joiner)
    )

    assert res.status_code == 409
