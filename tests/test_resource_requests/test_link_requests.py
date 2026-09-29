"""The request by the Admin's link — BE-26 (OBT-537), PR C.

The link's holder has no account: the link starts one open instance bound to it, writes it, and
submits it as the electronic acceptance; the trail names the link as author, never the Admin
who issued it; and the holder is told by e-mail — the link and its code, the receipt, the
decision — never in-app.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.rate_limit import limiter
from app.db.models.auth import App
from app.db.models.notification import Notification
from app.db.models.resource_request import RRRequest, RRRequestFieldHistory, RRRequestLink
from tests.baker import make_user
from tests.test_resource_requests.conftest import auth_header
from tests.test_resource_requests.test_evaluations import endorse, give_fund, put_evaluation
from tests.test_resource_requests.test_requests import REQUESTS, as_mesa, draft

LINKS = "/api/resource-requests/links"
PUBLIC = "/api/resource-requests/link"
START = f"{REQUESTS}/start"


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture()
def posted(monkeypatch) -> list[dict[str, str]]:
    sent: list[dict[str, str]] = []

    async def _record(*, to: str, subject: str, html: str, from_name: str | None = None) -> bool:
        sent.append({"to": to, "subject": subject, "html": html})
        return True

    monkeypatch.setattr("app.services.resource_request._notices.send_email", _record)
    return sent


async def holder(db_session, client, email: str = "equipe@fora.org"):
    """An Admin, a link they issued to ``email``, and the holder's link session."""
    admin = await make_user(db_session, email=f"admin-{email}", is_platform_admin=True)
    body = (
        await client.post(
            LINKS, json={"email": email}, headers=await auth_header(db_session, admin)
        )
    ).json()
    verified = await client.post(f"{PUBLIC}/{body['token']}/verify", json={"code": body["code"]})
    return admin, body, {"Authorization": f"Bearer {verified.json()['session']}"}


# ——— starting ——————————————————————————————————————————————————————————————————


async def test_a_link_starts_an_instance_bound_to_it(db_session, client, rrf_app) -> None:
    admin, link, headers = await holder(db_session, client)

    res = await client.post(START, json={"request_type": "traducao"}, headers=headers)

    assert res.status_code == 201, res.text
    assert res.json()["can_edit"] is True
    row = await db_session.get(RRRequest, res.json()["id"])
    assert row.request_link_id == link["id"]
    assert row.started_by_link_id == link["id"]
    assert row.started_by is None
    assert row.shema_project_id is None
    assert row.created_by == admin.id


async def test_a_link_names_no_project(db_session, client, rrf_app) -> None:
    _admin, _link, headers = await holder(db_session, client)

    res = await client.post(
        START, json={"request_type": "traducao", "project_id": "kadiweu"}, headers=headers
    )

    assert res.status_code == 422, res.text


async def test_one_open_instance_per_link_and_cancel_frees_it(db_session, client, rrf_app) -> None:
    _admin, _link, headers = await holder(db_session, client)
    first = (await client.post(START, json={"request_type": "traducao"}, headers=headers)).json()

    second = await client.post(START, json={"request_type": "traducao"}, headers=headers)
    older_door = await client.post(REQUESTS, json=draft(), headers=headers)
    cancelled = await client.post(f"{REQUESTS}/{first['id']}/cancel", headers=headers)
    again = await client.post(START, json={"request_type": "traducao"}, headers=headers)

    assert second.status_code == 409, second.text
    assert "link" in second.json()["detail"]
    assert older_door.status_code == 409
    assert cancelled.status_code == 200, cancelled.text
    assert again.status_code == 201, again.text


async def test_two_links_do_not_lock_each_other(db_session, client, rrf_app) -> None:
    _a, _la, a = await holder(db_session, client, "a@fora.org")
    _b, _lb, b = await holder(db_session, client, "b@fora.org")

    assert (
        await client.post(START, json={"request_type": "traducao"}, headers=a)
    ).status_code == 201
    assert (
        await client.post(START, json={"request_type": "traducao"}, headers=b)
    ).status_code == 201


# ——— writing ———————————————————————————————————————————————————————————————————


async def test_the_trail_names_the_link_and_never_the_admin(db_session, client, rrf_app) -> None:
    """GATE-02 D7's trail says who typed: the holder, through the link — not the Admin who
    issued it and is the request's bookkeeping owner."""
    admin, link, headers = await holder(db_session, client)
    started = (await client.post(REQUESTS, json=draft(), headers=headers)).json()
    changed = draft()
    changed["fields"]["reg_name"] = "pelo link"

    res = await client.patch(f"{REQUESTS}/{started['id']}", json=changed, headers=headers)

    assert res.status_code == 200, res.text
    rows = (
        (
            await db_session.execute(
                select(RRRequestFieldHistory).where(
                    RRRequestFieldHistory.request_id == started["id"]
                )
            )
        )
        .scalars()
        .all()
    )
    assert rows
    assert all(row.changed_by is None for row in rows)
    assert all(row.changed_by_link_id == link["id"] for row in rows)
    assert all(row.changed_by != admin.id for row in rows)


async def test_another_link_does_not_reach_the_instance(db_session, client, rrf_app) -> None:
    _a, _la, mine = await holder(db_session, client, "a@fora.org")
    _b, _lb, theirs = await holder(db_session, client, "b@fora.org")
    started = (await client.post(REQUESTS, json=draft(), headers=mine)).json()

    patched = await client.patch(f"{REQUESTS}/{started['id']}", json=draft(), headers=theirs)
    cancelled = await client.post(f"{REQUESTS}/{started['id']}/cancel", headers=theirs)
    submitted = await client.post(f"{REQUESTS}/{started['id']}/submit", headers=theirs)

    assert (patched.status_code, cancelled.status_code, submitted.status_code) == (404, 404, 404)


async def test_the_board_reads_a_link_request_and_does_not_write_it(
    db_session, client, rrf_app
) -> None:
    """BE-25's pen, unchanged by who started the instance: the mesa reads it."""
    _admin, _link, headers = await holder(db_session, client)
    started = (await client.post(REQUESTS, json=draft(), headers=headers)).json()
    mesa = await as_mesa(db_session, rrf_app)

    read = await client.get(f"{REQUESTS}/{started['id']}", headers=mesa)
    patched = await client.patch(f"{REQUESTS}/{started['id']}", json=draft(), headers=mesa)

    assert read.status_code == 200
    assert read.json()["can_edit"] is False
    assert patched.status_code == 403


async def test_the_issuing_admin_writes_it_as_an_admin(db_session, client, rrf_app) -> None:
    admin, _link, headers = await holder(db_session, client)
    started = (await client.post(REQUESTS, json=draft(), headers=headers)).json()

    res = await client.patch(
        f"{REQUESTS}/{started['id']}", json=draft(), headers=await auth_header(db_session, admin)
    )

    assert res.status_code == 200, res.text


# ——— submitting and being told ————————————————————————————————————————————————————


async def test_a_link_submits_and_the_holder_gets_a_receipt(
    db_session, client, rrf_app, posted
) -> None:
    _admin, link, headers = await holder(db_session, client)
    started = (await client.post(REQUESTS, json=draft(), headers=headers)).json()

    res = await client.post(f"{REQUESTS}/{started['id']}/submit", headers=headers)

    assert res.status_code == 200, res.text
    row = await db_session.get(RRRequest, started["id"])
    await db_session.refresh(row)
    assert row.submitted_at is not None
    assert row.started_by_link_id == link["id"]
    receipts = [letter for letter in posted if letter["to"] == "equipe@fora.org"]
    assert len(receipts) == 1
    assert "received" in receipts[0]["subject"].lower()
    assert "request link you received" in receipts[0]["html"]


async def test_the_decision_goes_to_the_link_by_email_and_to_nobody_in_app(
    db_session, client, rrf_app, posted
) -> None:
    admin, _link, headers = await holder(db_session, client)
    started = (await client.post(REQUESTS, json=draft(), headers=headers)).json()
    await client.post(f"{REQUESTS}/{started['id']}/submit", headers=headers)
    await endorse(db_session, started["id"])
    await give_fund(db_session, started["id"])
    posted.clear()

    res = await put_evaluation(
        client, await as_mesa(db_session, rrf_app), started["id"], decision="approved"
    )

    assert res.status_code == 200, res.text
    assert [letter["to"] for letter in posted] == ["equipe@fora.org"]
    admin_notices = (
        (
            await db_session.execute(
                select(Notification).where(
                    Notification.user_id == admin.id, Notification.event_type == "rr_decision"
                )
            )
        )
        .scalars()
        .all()
    )
    assert admin_notices == [], "the Admin is the request's bookkeeping owner, not its team"


async def test_issuing_a_link_mails_the_link_and_the_code(
    db_session, client, rrf_app, posted
) -> None:
    app = (await db_session.execute(select(App).where(App.id == rrf_app.id))).scalar_one()
    app.app_url = "https://form.example"
    await db_session.commit()
    admin = await make_user(db_session, email="admin@fora.org", is_platform_admin=True)

    body = (
        await client.post(
            LINKS,
            json={"email": "Equipe@Fora.org", "project_hint": "Kadiwéu"},
            headers=await auth_header(db_session, admin),
        )
    ).json()

    assert [letter["to"] for letter in posted] == ["equipe@fora.org"]
    assert f"https://form.example/solicitar/{body['token']}" in posted[0]["html"]
    assert body["code"] in posted[0]["html"]


async def test_with_no_app_url_no_letter_leaves_and_the_link_still_issues(
    db_session, client, rrf_app, posted
) -> None:
    admin = await make_user(db_session, email="admin@fora.org", is_platform_admin=True)

    res = await client.post(
        LINKS, json={"email": "equipe@fora.org"}, headers=await auth_header(db_session, admin)
    )

    assert res.status_code == 201
    assert posted == []
    assert await db_session.get(RRRequestLink, res.json()["id"]) is not None
