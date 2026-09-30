"""The base leader's endorsement by link — BE-23 (OBT-535).

The leader has no account (OBT-522, 22/set): the team types the leader's e-mail, submitting mails
that address a link and a code, and whoever confirms the code reads the frozen request and
endorses it. Grouped by where it fails: the **submission** — the address required and never the
requester's own, the link born with hashes only; the **code** — five wrong ones revoke, expired
and revoked are gone; the **act** — refused unverified and twice, stamped with the link; the
**Admin's resend**; and the **board** — no endorsement, no leaving ``triagem``.

⚠️ No negative test here uses a platform admin (``test_capabilities.py`` says why), except where
the Admin is the subject.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.rate_limit import limiter
from app.db.models.auth import App
from app.db.models.resource_request import (
    RRDecision,
    RREndorsementLink,
    RRRequest,
    RRSnapshot,
)
from app.services.common import tokens
from app.utils.stored_time import as_utc
from tests.baker import make_user
from tests.test_resource_requests.conftest import auth_header, grant
from tests.test_resource_requests.test_board import move
from tests.test_resource_requests.test_evaluations import give_fund
from tests.test_resource_requests.test_requests import (
    LEADER_EMAIL,
    REQUESTS,
    _decide,
    as_mesa,
    as_team,
    create,
    draft,
)

PUBLIC = "/api/resource-requests/endorse"


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture()
async def posted(db_session, rrf_app, monkeypatch) -> list[dict[str, str]]:
    """Every letter the module posts, with the form's ``app_url`` set so the link has a page."""
    app = (await db_session.execute(select(App).where(App.id == rrf_app.id))).scalar_one()
    app.app_url = "https://form.example"
    await db_session.commit()
    sent: list[dict[str, str]] = []

    async def _record(*, to: str, subject: str, html: str, from_name: str | None = None) -> bool:
        sent.append({"to": to, "subject": subject, "html": html})
        return True

    monkeypatch.setattr("app.services.resource_request._notices.send_email", _record)
    return sent


def secrets_in(letter: dict[str, str]) -> tuple[str, str]:
    """The token and the code, read back out of the letter the leader receives."""
    token = re.search(r"/endossar/([^\"]+)\"", letter["html"])
    code = re.search(r">(\d{6})<", letter["html"])
    assert token and code, letter["html"]
    return token.group(1), code.group(1)


def to_leader(posted: list[dict[str, str]]) -> list[dict[str, str]]:
    return [letter for letter in posted if letter["to"] == LEADER_EMAIL]


async def submitted(db_session, client, rrf_app) -> str:
    team = await as_team(db_session, rrf_app)
    created = await create(client, team)
    res = await client.post(f"{REQUESTS}/{created['id']}/submit", headers=team)
    assert res.status_code == 200, res.text
    return created["id"]


async def verified(client, token: str, code: str) -> None:
    res = await client.post(f"{PUBLIC}/{token}/verify", json={"code": code})
    assert res.status_code == 200, res.text


async def endorsed(client, posted: list[dict[str, str]], name: str = "Eva da Base") -> str:
    token, code = secrets_in(to_leader(posted)[-1])
    await verified(client, token, code)
    res = await client.post(f"{PUBLIC}/{token}", json={"leader_name": name})
    assert res.status_code == 200, res.text
    return token


def wrong(code: str) -> str:
    return "999999" if code != "999999" else "000000"


async def as_admin(db_session) -> dict[str, str]:
    return await auth_header(
        db_session, await make_user(db_session, email="admin@rr.org", is_platform_admin=True)
    )


# ——— the submission ——————————————————————————————————————————————————————————————


async def test_submitting_without_the_leaders_email_is_refused_on_the_field(
    db_session, client, rrf_app
) -> None:
    team = await as_team(db_session, rrf_app)
    created = await create(client, team, leader_email="")

    res = await client.post(f"{REQUESTS}/{created['id']}/submit", headers=team)

    assert res.status_code == 400, res.text
    assert ["leader_email"] in [error["loc"] for error in res.json()["errors"]]


@pytest.mark.parametrize("spelling", ["equipe@rr.org", "Equipe@RR.org"])
async def test_the_requester_never_endorses(db_session, client, rrf_app, spelling: str) -> None:
    """*Solicitante nunca endossa* — Daniel, 23/set — under any spelling of the address."""
    team = await as_team(db_session, rrf_app, email="equipe@rr.org")
    created = await create(client, team, leader_email=spelling)

    res = await client.post(f"{REQUESTS}/{created['id']}/submit", headers=team)

    assert res.status_code == 400, res.text
    assert "never endorses" in res.text


async def test_a_malformed_address_is_refused_while_typing(db_session, client, rrf_app) -> None:
    team = await as_team(db_session, rrf_app)

    res = await client.post(REQUESTS, json=draft(leader_email="sem-arroba"), headers=team)

    assert res.status_code == 422


async def test_no_link_exists_before_the_form_is_submitted(db_session, client, rrf_app) -> None:
    """*"O link só pode ficar disponível após todo o forms ser preenchido"* — Daniel, 25/set."""
    team = await as_team(db_session, rrf_app)
    await create(client, team)

    assert (await db_session.execute(select(RREndorsementLink))).scalars().all() == []


async def test_submitting_issues_the_link_hashed_and_mails_it_to_the_leader(
    db_session, client, rrf_app, posted
) -> None:
    request_id = await submitted(db_session, client, rrf_app)

    letters = to_leader(posted)
    assert len(letters) == 1
    token, code = secrets_in(letters[0])
    link = (await db_session.execute(select(RREndorsementLink))).scalar_one()
    assert link.request_id == request_id
    assert link.email == LEADER_EMAIL
    assert link.token_hash == tokens.digest(token)
    assert link.code_hash == tokens.digest(code)
    assert token not in (link.token_hash, link.code_hash)
    life = as_utc(link.expires_at) - datetime.now(UTC)
    assert timedelta(days=13) < life <= timedelta(days=14, minutes=1)


async def test_with_no_app_url_the_link_exists_and_no_letter_leaves(
    db_session, client, rrf_app, monkeypatch
) -> None:
    sent: list[str] = []

    async def _record(*, to: str, **_: object) -> bool:
        sent.append(to)
        return True

    monkeypatch.setattr("app.services.resource_request._notices.send_email", _record)
    await submitted(db_session, client, rrf_app)

    assert LEADER_EMAIL not in sent
    assert (await db_session.execute(select(RREndorsementLink))).scalar_one() is not None


# ——— the code ——————————————————————————————————————————————————————————————————


async def test_before_the_code_the_page_shows_the_state_and_not_the_request(
    db_session, client, rrf_app, posted
) -> None:
    await submitted(db_session, client, rrf_app)
    token, _ = secrets_in(to_leader(posted)[0])

    res = await client.get(f"{PUBLIC}/{token}")

    assert res.status_code == 200, res.text
    assert res.json()["status"] == "pending"
    assert res.json()["email_hint"] == "l***@base.org"
    assert res.json()["document"] is None


async def test_an_unknown_token_is_404(client, rrf_app) -> None:
    assert (await client.get(f"{PUBLIC}/nao-existe")).status_code == 404
    assert (
        await client.post(f"{PUBLIC}/nao-existe/verify", json={"code": "000000"})
    ).status_code == 404
    assert (
        await client.post(f"{PUBLIC}/nao-existe", json={"leader_name": "Eva"})
    ).status_code == 404


async def test_the_right_code_opens_the_frozen_request(db_session, client, rrf_app, posted) -> None:
    """The leader reads what the team submitted — the snapshot — and nothing of the mesa's."""
    request_id = await submitted(db_session, client, rrf_app)
    token, code = secrets_in(to_leader(posted)[0])

    await verified(client, token, code)
    page = (await client.get(f"{PUBLIC}/{token}")).json()

    snapshot = (
        await db_session.execute(select(RRSnapshot).where(RRSnapshot.request_id == request_id))
    ).scalar_one()
    assert page["status"] == "verified"
    assert page["document"] == snapshot.document
    assert not {"scores", "decision", "comments", "team_note"} & set(page["document"])


async def test_five_wrong_codes_revoke_the_link(db_session, client, rrf_app, posted) -> None:
    await submitted(db_session, client, rrf_app)
    token, code = secrets_in(to_leader(posted)[0])

    answers = [
        await client.post(f"{PUBLIC}/{token}/verify", json={"code": wrong(code)}) for _ in range(5)
    ]
    after = await client.post(f"{PUBLIC}/{token}/verify", json={"code": code})

    assert [a.status_code for a in answers] == [401, 401, 401, 401, 410]
    assert [a.json().get("attempts_left") for a in answers[:4]] == [4, 3, 2, 1]
    assert after.status_code == 410, "the right code does not reopen a revoked link"
    assert (await client.get(f"{PUBLIC}/{token}")).json()["status"] == "revoked"


async def test_the_right_code_zeroes_the_count(db_session, client, rrf_app, posted) -> None:
    await submitted(db_session, client, rrf_app)
    token, code = secrets_in(to_leader(posted)[0])

    for _ in range(4):
        await client.post(f"{PUBLIC}/{token}/verify", json={"code": wrong(code)})
    await verified(client, token, code)
    again = [
        (await client.post(f"{PUBLIC}/{token}/verify", json={"code": wrong(code)})).status_code
        for _ in range(4)
    ]

    assert again == [401, 401, 401, 401]


@pytest.mark.parametrize("state", ["expired", "revoked"])
async def test_an_expired_or_revoked_link_is_gone(
    db_session, client, rrf_app, posted, state: str
) -> None:
    await submitted(db_session, client, rrf_app)
    token, code = secrets_in(to_leader(posted)[0])
    await verified(client, token, code)
    link = (await db_session.execute(select(RREndorsementLink))).scalar_one()
    if state == "expired":
        link.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    else:
        link.revoked_at = datetime.now(UTC)
    await db_session.commit()

    read = await client.get(f"{PUBLIC}/{token}")
    verify = await client.post(f"{PUBLIC}/{token}/verify", json={"code": code})
    endorse = await client.post(f"{PUBLIC}/{token}", json={"leader_name": "Eva"})

    assert read.json()["status"] == state
    assert read.json()["document"] is None
    assert (verify.status_code, endorse.status_code) == (410, 410)
    assert endorse.json()["code"] == "ENDORSEMENT_LINK_GONE"


# ——— the act ———————————————————————————————————————————————————————————————————


async def test_endorsing_without_the_code_is_refused(db_session, client, rrf_app, posted) -> None:
    request_id = await submitted(db_session, client, rrf_app)
    token, _ = secrets_in(to_leader(posted)[0])

    res = await client.post(f"{PUBLIC}/{token}", json={"leader_name": "Eva da Base"})

    assert res.status_code == 403, res.text
    assert (await db_session.get(RRRequest, request_id)).endorsed_at is None


async def test_endorsing_stamps_the_link_the_name_and_the_day(
    db_session, client, rrf_app, posted
) -> None:
    request_id = await submitted(db_session, client, rrf_app)

    token = await endorsed(client, posted, name="  Eva da Base ")

    row = await db_session.get(RRRequest, request_id)
    await db_session.refresh(row)
    link = (await db_session.execute(select(RREndorsementLink))).scalar_one()
    await db_session.refresh(link)
    assert row.endorsed_at is not None
    assert row.endorsed_email == LEADER_EMAIL
    assert row.endorsement_link_id == link.id
    assert row.endorsed_by is None, "there is no account behind the act"
    assert row.leader_name == "Eva da Base"
    assert row.leader_date == as_utc(row.endorsed_at).date()
    assert link.used_at is not None
    assert (await client.get(f"{PUBLIC}/{token}")).json()["status"] == "endorsed"


async def test_the_team_sees_who_endorsed_and_when(db_session, client, rrf_app, posted) -> None:
    team = await as_team(db_session, rrf_app)
    created = await create(client, team)
    await client.post(f"{REQUESTS}/{created['id']}/submit", headers=team)
    await endorsed(client, posted)

    read = (await client.get(f"{REQUESTS}/{created['id']}", headers=team)).json()

    assert read["endorsed_email"] == LEADER_EMAIL
    assert read["endorsed_at"] is not None
    assert read["document"]["fields"]["leader_name"] == "Eva da Base"


async def test_endorsing_twice_is_refused(db_session, client, rrf_app, posted) -> None:
    request_id = await submitted(db_session, client, rrf_app)
    token = await endorsed(client, posted)

    again = await client.post(f"{PUBLIC}/{token}", json={"leader_name": "Outra Pessoa"})

    assert again.status_code == 409, again.text
    row = await db_session.get(RRRequest, request_id)
    await db_session.refresh(row)
    assert row.leader_name == "Eva da Base"


async def test_the_leader_can_reread_what_was_signed(db_session, client, rrf_app, posted) -> None:
    await submitted(db_session, client, rrf_app)
    token = await endorsed(client, posted)

    assert (await client.get(f"{PUBLIC}/{token}")).json()["document"] is not None


async def test_an_endorsed_link_reads_endorsed_past_its_clock_and_stops_serving_the_request(
    db_session, client, rrf_app, posted
) -> None:
    """The fact outlives the link, the document does not (PR #579, review): the invite's
    order, *used* before *expired*, for a link spent by one act."""
    await submitted(db_session, client, rrf_app)
    token = await endorsed(client, posted)
    _, code = secrets_in(to_leader(posted)[0])
    link = (await db_session.execute(select(RREndorsementLink))).scalar_one()
    link.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    await db_session.commit()

    page = (await client.get(f"{PUBLIC}/{token}")).json()
    again = await client.post(f"{PUBLIC}/{token}", json={"leader_name": "Outra Pessoa"})
    verify = await client.post(f"{PUBLIC}/{token}/verify", json={"code": code})

    assert page["status"] == "endorsed"
    assert page["document"] is None
    assert again.status_code == 409, "told it is endorsed, not that the link is gone"
    assert verify.status_code == 410


async def test_wrong_codes_on_a_spent_link_do_not_undo_the_endorsement(
    db_session, client, rrf_app, posted
) -> None:
    await submitted(db_session, client, rrf_app)
    token = await endorsed(client, posted)
    _, code = secrets_in(to_leader(posted)[0])

    for _ in range(5):
        await client.post(f"{PUBLIC}/{token}/verify", json={"code": wrong(code)})

    page = (await client.get(f"{PUBLIC}/{token}")).json()
    assert page["status"] == "endorsed"
    assert page["document"] is None


async def test_the_old_account_route_is_gone(db_session, client, rrf_app) -> None:
    request_id = await submitted(db_session, client, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)

    res = await client.post(f"{REQUESTS}/{request_id}/endorse", headers=mesa)

    assert res.status_code in (404, 405)


# ——— the Admin's resend ———————————————————————————————————————————————————————————


async def test_the_admin_resends_and_the_old_link_dies(db_session, client, rrf_app, posted) -> None:
    request_id = await submitted(db_session, client, rrf_app)
    old_token, _ = secrets_in(to_leader(posted)[0])

    res = await client.post(
        f"{REQUESTS}/{request_id}/endorsement/resend", headers=await as_admin(db_session)
    )

    assert res.status_code == 200, res.text
    assert res.json() == {"sent": True}, "no secret comes back to the Admin"
    assert (await client.get(f"{PUBLIC}/{old_token}")).json()["status"] == "revoked"
    new_token, new_code = secrets_in(to_leader(posted)[-1])
    assert new_token != old_token
    await verified(client, new_token, new_code)


@pytest.mark.parametrize("role", ["mesa", "gestor", "equipe"])
async def test_nobody_but_the_admin_resends(db_session, client, rrf_app, role: str) -> None:
    request_id = await submitted(db_session, client, rrf_app)
    user = await make_user(db_session, email=f"{role}@outro.org")
    await grant(db_session, user, rrf_app, role)

    res = await client.post(
        f"{REQUESTS}/{request_id}/endorsement/resend", headers=await auth_header(db_session, user)
    )

    assert res.status_code == 403


async def test_an_endorsed_request_or_a_draft_is_not_resent(
    db_session, client, rrf_app, posted
) -> None:
    team = await as_team(db_session, rrf_app, email="outra@rr.org")
    moving = await create(client, team)
    request_id = await submitted(db_session, client, rrf_app)
    await endorsed(client, posted)
    admin = await as_admin(db_session)

    signed = await client.post(f"{REQUESTS}/{request_id}/endorsement/resend", headers=admin)
    unsent = await client.post(f"{REQUESTS}/{moving['id']}/endorsement/resend", headers=admin)

    assert (signed.status_code, unsent.status_code) == (409, 409)


async def test_a_request_with_no_leader_is_not_resent(db_session, client, rrf_app, posted) -> None:
    """Every request submitted before ``20260930_rr12`` names nobody (PR #579, review): a link
    addressed to ``""`` is not a resend, and ``sent`` would have claimed a letter left."""
    request_id = await submitted(db_session, client, rrf_app)
    row = await db_session.get(RRRequest, request_id)
    row.leader_email = ""
    await db_session.commit()
    before = len(posted)

    res = await client.post(
        f"{REQUESTS}/{request_id}/endorsement/resend", headers=await as_admin(db_session)
    )

    assert res.status_code == 409, res.text
    assert "no base leader" in res.json()["detail"]
    assert len(posted) == before


async def test_sent_is_what_the_provider_accepted(
    db_session, client, rrf_app, posted, monkeypatch
) -> None:
    request_id = await submitted(db_session, client, rrf_app)

    async def _refused(**_: object) -> bool:
        return False

    monkeypatch.setattr("app.services.resource_request._notices.send_email", _refused)

    res = await client.post(
        f"{REQUESTS}/{request_id}/endorsement/resend", headers=await as_admin(db_session)
    )

    assert res.status_code == 200, res.text
    assert res.json() == {"sent": False}


# ——— a revision, and the board ——————————————————————————————————————————————————————


async def test_a_revision_keeps_the_address_and_needs_a_new_endorsement(
    db_session, client, rrf_app, posted
) -> None:
    team = await as_team(db_session, rrf_app)
    created = await create(client, team)
    await client.post(f"{REQUESTS}/{created['id']}/submit", headers=team)
    await endorsed(client, posted)
    await _decide(db_session, created["id"], RRDecision.REVISE)

    revision = (await client.post(f"{REQUESTS}/{created['id']}/revise", headers=team)).json()

    assert revision["document"]["leader_email"] == LEADER_EMAIL
    assert revision["endorsed_at"] is None
    assert revision["endorsed_email"] is None
    await client.post(f"{REQUESTS}/{revision['id']}/submit", headers=team)
    assert len(to_leader(posted)) == 2, "the revision's submission issues its own link"


async def test_endorsed_by_link_the_card_leaves_triagem(
    db_session, client, rrf_app, posted
) -> None:
    """The board half of the DoD: ``guard_endorsement`` already existed (BE-16, enforced on
    4/set/2026) and reads ``endorsed_at``, so the link's act is what opens ``analise``. The
    refusal without it is ``test_board.py``'s ``test_um_pedido_sem_endosso_nao_sai_da_triagem``."""
    request_id = await submitted(db_session, client, rrf_app)
    await give_fund(db_session, request_id)
    mesa = await as_mesa(db_session, rrf_app)

    before = await move(client, mesa, request_id, "analise")
    await endorsed(client, posted)
    after = await move(client, mesa, request_id, "analise")

    assert before.status_code == 409, before.text
    assert after.status_code == 200, after.text
    assert after.json()["stage"] == "analise"
