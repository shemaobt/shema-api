"""The request link's public door and the link session — BE-26 (OBT-537), PR B.

A link's state is read, never refused; its code trades for a link session, five wrong ones
revoke it; and the session reads **its own link's** requests — never another link's, never a
project's — through the same four routes an account reads with.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.core.rate_limit import limiter
from app.db.models.resource_request import RRRequest, RRRequestLink, RRRequestSections
from app.services.resource_request.link_session import encode_link_session, link_session_subject
from tests.baker import make_user
from tests.test_resource_requests.conftest import auth_header, make_membership
from tests.test_resource_requests.test_requests import REQUESTS, draft

LINKS = "/api/resource-requests/links"
PUBLIC = "/api/resource-requests/link"


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter.reset()
    yield
    limiter.reset()


async def issued_link(db_session, client, email: str = "Equipe@Fora.org"):
    admin = await make_user(db_session, email=f"admin-{email.lower()}", is_platform_admin=True)
    body = (
        await client.post(
            LINKS,
            json={"email": email, "project_hint": "equipe X"},
            headers=await auth_header(db_session, admin),
        )
    ).json()
    return admin, body


async def session_for(client, body) -> dict[str, str]:
    res = await client.post(f"{PUBLIC}/{body['token']}/verify", json={"code": body["code"]})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['session']}"}


async def request_of_link(db_session, admin, link_id: str) -> str:
    row = RRRequest(
        request_type="traducao",
        created_by=admin.id,
        request_link_id=link_id,
        started_by_link_id=link_id,
    )
    db_session.add(row)
    await db_session.flush()
    db_session.add(RRRequestSections(request_id=row.id, content={}))
    await db_session.commit()
    return row.id


# ——— the public state ——————————————————————————————————————————————————————————


async def test_a_link_reads_its_state_with_the_address_masked(db_session, client, rrf_app) -> None:
    _admin, body = await issued_link(db_session, client)

    res = await client.get(f"{PUBLIC}/{body['token']}")

    assert res.status_code == 200, res.text
    assert res.json()["status"] == "pending"
    assert res.json()["email_hint"] == "e***@fora.org"
    assert res.json()["project_hint"] == "equipe X"


async def test_an_unknown_token_is_404(client, rrf_app) -> None:
    assert (await client.get(f"{PUBLIC}/nao-existe")).status_code == 404
    assert (
        await client.post(f"{PUBLIC}/nao-existe/verify", json={"code": "000000"})
    ).status_code == 404


async def test_an_old_link_reads_as_what_it_is(db_session, client, rrf_app) -> None:
    """Expired and revoked are read, not refused: opening an old e-mail is no fault."""
    _admin, body = await issued_link(db_session, client)
    link = await db_session.get(RRRequestLink, body["id"])
    link.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    await db_session.commit()

    assert (await client.get(f"{PUBLIC}/{body['token']}")).json()["status"] == "expired"


# ——— the code ——————————————————————————————————————————————————————————————————


async def test_the_right_code_answers_a_session_and_marks_the_link_verified(
    db_session, client, rrf_app
) -> None:
    _admin, body = await issued_link(db_session, client)

    res = await client.post(f"{PUBLIC}/{body['token']}/verify", json={"code": body["code"]})

    assert res.status_code == 200, res.text
    assert link_session_subject(res.json()["session"]) == body["id"]
    link = await db_session.get(RRRequestLink, body["id"])
    await db_session.refresh(link)
    assert link.verified_at is not None


async def test_verifying_again_from_another_phone_is_legitimate(
    db_session, client, rrf_app
) -> None:
    _admin, body = await issued_link(db_session, client)

    first = await client.post(f"{PUBLIC}/{body['token']}/verify", json={"code": body["code"]})
    second = await client.post(f"{PUBLIC}/{body['token']}/verify", json={"code": body["code"]})

    assert (first.status_code, second.status_code) == (200, 200)


async def test_a_wrong_code_counts_and_the_fifth_revokes(db_session, client, rrf_app) -> None:
    _admin, body = await issued_link(db_session, client)
    wrong = "999999" if body["code"] != "999999" else "000000"

    answers = [
        await client.post(f"{PUBLIC}/{body['token']}/verify", json={"code": wrong})
        for _ in range(5)
    ]
    after = await client.post(f"{PUBLIC}/{body['token']}/verify", json={"code": body["code"]})

    assert [a.status_code for a in answers] == [401, 401, 401, 401, 410]
    assert [a.json().get("attempts_left") for a in answers[:4]] == [4, 3, 2, 1]
    assert after.status_code == 410, "the right code does not reopen a revoked link"
    link = await db_session.get(RRRequestLink, body["id"])
    await db_session.refresh(link)
    assert link.revoked_at is not None


@pytest.mark.parametrize("state", ["expired", "revoked"])
async def test_an_expired_or_revoked_link_is_410(db_session, client, rrf_app, state: str) -> None:
    _admin, body = await issued_link(db_session, client)
    link = await db_session.get(RRRequestLink, body["id"])
    if state == "expired":
        link.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    else:
        link.revoked_at = datetime.now(UTC)
    await db_session.commit()

    res = await client.post(f"{PUBLIC}/{body['token']}/verify", json={"code": body["code"]})

    assert res.status_code == 410
    assert res.json()["code"] == "LINK_GONE"


# ——— what the session reaches ——————————————————————————————————————————————————


async def test_a_session_reads_its_own_links_requests_and_nothing_else(
    db_session, client, rrf_app
) -> None:
    admin, mine = await issued_link(db_session, client, "a@fora.org")
    _other_admin, theirs = await issued_link(db_session, client, "b@fora.org")
    own = await request_of_link(db_session, admin, mine["id"])
    foreign = await request_of_link(db_session, admin, theirs["id"])
    member = await make_user(db_session, email="membro@fora.org")
    await make_membership(db_session, member, "kadiweu")
    project = (
        await client.post(REQUESTS, json=draft(), headers=await auth_header(db_session, member))
    ).json()["id"]
    headers = await session_for(client, mine)

    listed = [row["id"] for row in (await client.get(REQUESTS, headers=headers)).json()]
    cards = [row["id"] for row in (await client.get(f"{REQUESTS}/cards", headers=headers)).json()]

    assert listed == [own]
    assert cards == [own]
    assert (await client.get(f"{REQUESTS}/{own}", headers=headers)).status_code == 200
    assert (await client.get(f"{REQUESTS}/{own}/status", headers=headers)).status_code == 200
    for other in (foreign, project):
        assert (await client.get(f"{REQUESTS}/{other}", headers=headers)).status_code == 404
        assert (await client.get(f"{REQUESTS}/{other}/status", headers=headers)).status_code == 404


async def test_a_session_writes_only_what_its_link_started(db_session, client, rrf_app) -> None:
    """``can_edit`` for a link: its own open instance. The writes themselves are PR C's."""
    admin, body = await issued_link(db_session, client)
    own = await request_of_link(db_session, admin, body["id"])
    headers = await session_for(client, body)

    read = (await client.get(f"{REQUESTS}/{own}", headers=headers)).json()

    assert read["can_edit"] is True
    assert "fund_id" not in read, "a link never reads the fund"


async def test_a_revoked_link_ends_every_session_it_opened(db_session, client, rrf_app) -> None:
    admin, body = await issued_link(db_session, client)
    await request_of_link(db_session, admin, body["id"])
    headers = await session_for(client, body)
    await client.post(f"{LINKS}/{body['id']}/revoke", headers=await auth_header(db_session, admin))

    assert (await client.get(REQUESTS, headers=headers)).status_code == 401


async def test_a_session_opens_no_route_but_the_four_reads(db_session, client, rrf_app) -> None:
    """Every other route keeps its user-only guard: a link session is refused there."""
    admin, body = await issued_link(db_session, client)
    own = await request_of_link(db_session, admin, body["id"])
    headers = await session_for(client, body)

    assert (
        await client.patch(f"{REQUESTS}/{own}", json=draft(), headers=headers)
    ).status_code == 401
    assert (await client.get(LINKS, headers=headers)).status_code == 401
    assert (await client.get("/api/auth/me", headers=headers)).status_code == 401


async def test_a_user_token_is_never_read_as_a_link_session(db_session, rrf_app) -> None:
    user = await make_user(db_session, email="conta@fora.org")
    token = (await auth_header(db_session, user))["Authorization"].removeprefix("Bearer ")

    assert link_session_subject(token) is None


async def test_a_session_for_a_link_that_does_not_exist_is_401(client, rrf_app) -> None:
    token, _ = encode_link_session("nao-existe")

    res = await client.get(REQUESTS, headers={"Authorization": f"Bearer {token}"})

    assert res.status_code == 401


async def test_the_right_code_zeroes_the_count(db_session, client, rrf_app) -> None:
    """A second phone that mistyped four times and then got it right must not leave the link
    one try from revocation for everyone else (PR #577, review)."""
    _admin, body = await issued_link(db_session, client)
    wrong = "999999" if body["code"] != "999999" else "000000"

    async def wrong_four_times() -> list[int]:
        return [
            (
                await client.post(f"{PUBLIC}/{body['token']}/verify", json={"code": wrong})
            ).status_code
            for _ in range(4)
        ]

    first = await wrong_four_times()
    await client.post(f"{PUBLIC}/{body['token']}/verify", json={"code": body["code"]})
    second = await wrong_four_times()

    assert first == second == [401, 401, 401, 401]
    link = await db_session.get(RRRequestLink, body["id"])
    await db_session.refresh(link)
    assert link.revoked_at is None


async def test_the_session_never_outlives_its_link(db_session, client, rrf_app) -> None:
    """Verifying ten days before the link ends answers those ten days, not thirty."""
    _admin, body = await issued_link(db_session, client)
    link = await db_session.get(RRRequestLink, body["id"])
    link.expires_at = datetime.now(UTC) + timedelta(days=10)
    await db_session.commit()

    res = await client.post(f"{PUBLIC}/{body['token']}/verify", json={"code": body["code"]})

    expires = datetime.fromisoformat(res.json()["expires_at"])
    assert expires <= datetime.now(UTC) + timedelta(days=10, minutes=1)
