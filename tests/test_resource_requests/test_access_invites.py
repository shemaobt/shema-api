"""The link door: an invitation that exists before its person does.

Built from scratch for OBT-477 — ``ProjectInvite`` refuses an e-mail with no
active user, which is exactly whom a link serves. Covered here: who may write
one, the single raw token that never touches the database, the public lookup
that routes a stranger to signup, single use, expiry, revocation, and the
letter leaving through BE-12's door *after* the row is committed.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select

from app.core.config import get_settings
from app.db.models.auth import AccessInvite
from tests.baker import make_user
from tests.test_email_infra import _client_class
from tests.test_resource_requests.conftest import auth_header, grant

ACCESS = "/api/resource-requests/access"


async def _gestor(db_session, rrf_app, email: str = "inviter@rrf.test"):
    user = await make_user(db_session, email=email)
    await grant(db_session, user, rrf_app, "gestor")
    return user, await auth_header(db_session, user)


async def _admin(db_session, email: str = "padmin@rrf.test"):
    user = await make_user(db_session, email=email, is_platform_admin=True)
    return user, await auth_header(db_session, user)


async def _invite(client, headers, email: str = "stranger@rrf.test", role_key: str = "equipe"):
    res = await client.post(
        f"{ACCESS}/invites", json={"email": email, "role_key": role_key}, headers=headers
    )
    assert res.status_code == 201, res.text
    return res.json()


def _token_of(body: dict) -> str:
    return body["invite_url"].split("token=")[1]


async def test_a_gestor_invites_and_only_the_hash_lands_in_the_database(
    db_session, client, rrf_app
) -> None:
    _inviter, headers = await _gestor(db_session, rrf_app)

    body = await _invite(client, headers)

    token = _token_of(body)
    row = (await db_session.execute(select(AccessInvite))).scalar_one()
    assert row.email == "stranger@rrf.test"
    assert row.token_hash != token
    assert token not in row.token_hash
    assert body["status"] == "pending"


async def test_the_letter_leaves_through_be12s_door_with_the_link_inside(
    db_session, client, rrf_app, monkeypatch
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "email_provider", "resend")
    monkeypatch.setattr(settings, "resend_api_key", "test-key")
    recorded: list = []
    monkeypatch.setattr(httpx, "AsyncClient", _client_class(recorded))
    _inviter, headers = await _gestor(db_session, rrf_app)

    body = await _invite(client, headers)

    [(url, kwargs)] = recorded
    assert url == "https://api.resend.com/emails"
    payload = kwargs["json"]
    assert payload["to"] == ["stranger@rrf.test"]
    assert body["invite_url"] in payload["html"]


async def test_a_dead_provider_does_not_revert_the_committed_invite(
    db_session, client, rrf_app, monkeypatch
) -> None:
    """The e-mail fires outside the transaction; the creator keeps the link."""
    settings = get_settings()
    monkeypatch.setattr(settings, "email_provider", "resend")
    monkeypatch.setattr(settings, "resend_api_key", "test-key")
    monkeypatch.setattr(
        httpx, "AsyncClient", _client_class([], error=httpx.ConnectError("provider down"))
    )
    _inviter, headers = await _gestor(db_session, rrf_app)

    body = await _invite(client, headers)

    row = (await db_session.execute(select(AccessInvite))).scalar_one()
    assert row.email == "stranger@rrf.test"
    assert "token=" in body["invite_url"]


async def test_equipe_cannot_invite_and_inviting_yourself_is_refused(
    db_session, client, rrf_app
) -> None:
    equipe = await make_user(db_session, email="equipe@rrf.test")
    await grant(db_session, equipe, rrf_app, "equipe")
    equipe_headers = await auth_header(db_session, equipe)
    gestor, gestor_headers = await _gestor(db_session, rrf_app)

    below = await client.post(
        f"{ACCESS}/invites",
        json={"email": "x@rrf.test", "role_key": "equipe"},
        headers=equipe_headers,
    )
    themselves = await client.post(
        f"{ACCESS}/invites",
        json={"email": gestor.email, "role_key": "mesa"},
        headers=gestor_headers,
    )

    assert below.status_code == 403
    assert themselves.status_code == 400


async def test_a_second_pending_invite_for_the_same_email_and_role_is_refused(
    db_session, client, rrf_app
) -> None:
    _inviter, headers = await _gestor(db_session, rrf_app)
    await _invite(client, headers)

    res = await client.post(
        f"{ACCESS}/invites",
        json={"email": "stranger@rrf.test", "role_key": "equipe"},
        headers=headers,
    )

    assert res.status_code == 409


async def test_the_public_lookup_sends_a_stranger_to_signup(db_session, client, rrf_app) -> None:
    """No auth header anywhere in this test — the endpoint's whole point."""
    _inviter, headers = await _gestor(db_session, rrf_app)
    body = await _invite(client, headers)

    res = await client.get(f"{ACCESS}/invites/{_token_of(body)}")

    assert res.status_code == 200
    description = res.json()
    assert description["status"] == "pending"
    assert description["email"] == "stranger@rrf.test"
    assert description["account_exists"] is False
    assert description["role_key"] == "equipe"
    assert description["app_name"] == "Resource Request Form"


async def test_the_public_lookup_recognises_an_existing_account(
    db_session, client, rrf_app
) -> None:
    _inviter, headers = await _gestor(db_session, rrf_app)
    await make_user(db_session, email="known@rrf.test")
    body = await _invite(client, headers, email="known@rrf.test")

    res = await client.get(f"{ACCESS}/invites/{_token_of(body)}")

    assert res.json()["account_exists"] is True


async def test_an_unknown_token_is_a_404(client, rrf_app) -> None:
    res = await client.get(f"{ACCESS}/invites/deadbeef")
    assert res.status_code == 404


async def test_accepting_grants_the_role_in_the_inviters_name_and_spends_the_invite(
    db_session, client, rrf_app
) -> None:
    inviter, headers = await _gestor(db_session, rrf_app)
    body = await _invite(client, headers, role_key="mesa")
    token = _token_of(body)
    joiner = await make_user(db_session, email="stranger@rrf.test")
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
    _inviter, headers = await _gestor(db_session, rrf_app)
    body = await _invite(client, headers)
    other = await make_user(db_session, email="someone-else@rrf.test")

    res = await client.post(
        f"{ACCESS}/invites/{_token_of(body)}/accept",
        headers=await auth_header(db_session, other),
    )

    assert res.status_code == 403


async def test_an_expired_invite_neither_reads_pending_nor_accepts(
    db_session, client, rrf_app
) -> None:
    _inviter, headers = await _gestor(db_session, rrf_app)
    body = await _invite(client, headers)
    token = _token_of(body)
    row = (await db_session.execute(select(AccessInvite))).scalar_one()
    row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    await db_session.commit()
    joiner = await make_user(db_session, email="stranger@rrf.test")

    lookup = await client.get(f"{ACCESS}/invites/{token}")
    accept = await client.post(
        f"{ACCESS}/invites/{token}/accept", headers=await auth_header(db_session, joiner)
    )

    assert lookup.json()["status"] == "expired"
    assert accept.status_code == 409


async def test_only_the_admin_recalls_a_pending_invite_and_the_door_stays_shut(
    db_session, client, rrf_app
) -> None:
    """Access revoked before anyone accepted: the pending invite is closed here,
    and the person arriving later meets 409, not a grant."""
    _inviter, gestor_headers = await _gestor(db_session, rrf_app)
    body = await _invite(client, gestor_headers)
    token = _token_of(body)
    admin, admin_headers = await _admin(db_session)

    by_gestor = await client.post(
        f"{ACCESS}/invites/revoke", json={"invite_id": body["id"]}, headers=gestor_headers
    )
    by_admin = await client.post(
        f"{ACCESS}/invites/revoke", json={"invite_id": body["id"]}, headers=admin_headers
    )

    assert by_gestor.status_code == 403
    assert by_admin.status_code == 200
    assert by_admin.json()["status"] == "revoked"

    row = (await db_session.execute(select(AccessInvite))).scalar_one()
    assert row.revoked_by == admin.id

    joiner = await make_user(db_session, email="stranger@rrf.test")
    accept = await client.post(
        f"{ACCESS}/invites/{token}/accept", headers=await auth_header(db_session, joiner)
    )
    assert accept.status_code == 409
    assert (await client.get(f"{ACCESS}/invites/{token}")).json()["status"] == "revoked"


async def test_an_accepted_invite_is_past_recalling(db_session, client, rrf_app) -> None:
    _inviter, headers = await _gestor(db_session, rrf_app)
    body = await _invite(client, headers)
    joiner = await make_user(db_session, email="stranger@rrf.test")
    accepted = await client.post(
        f"{ACCESS}/invites/{_token_of(body)}/accept",
        headers=await auth_header(db_session, joiner),
    )
    assert accepted.status_code == 200
    _admin_user, admin_headers = await _admin(db_session)

    res = await client.post(
        f"{ACCESS}/invites/revoke", json={"invite_id": body["id"]}, headers=admin_headers
    )

    assert res.status_code == 409


async def test_exclusivity_holds_at_acceptance_time_too(db_session, client, rrf_app) -> None:
    """The holder's roles may change between the letter and the click."""
    _inviter, headers = await _gestor(db_session, rrf_app)
    body = await _invite(client, headers, role_key="mesa")
    joiner = await make_user(db_session, email="stranger@rrf.test")
    await grant(db_session, joiner, rrf_app, "gestor")

    res = await client.post(
        f"{ACCESS}/invites/{_token_of(body)}/accept",
        headers=await auth_header(db_session, joiner),
    )

    assert res.status_code == 409


async def test_open_invites_appear_on_the_overview_with_their_status(
    db_session, client, rrf_app
) -> None:
    _inviter, headers = await _gestor(db_session, rrf_app)
    body = await _invite(client, headers)

    res = await client.get(ACCESS, headers=headers)

    assert res.status_code == 200
    invites = res.json()["invites"]
    assert [(i["id"], i["email"], i["status"]) for i in invites] == [
        (body["id"], "stranger@rrf.test", "pending")
    ]
