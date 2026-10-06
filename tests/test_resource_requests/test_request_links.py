"""The Admin's request links: issue, list, revoke — BE-26 (OBT-537), first slice.

Only the Admin — the platform admin, or ``admin`` in either app (OBT-522) — issues, lists and
revokes. The token and the code leave once, in the answer that issued them, and only their
digests are stored. The schema half — a request's ``request_link_id`` and the one-open-per-link
index — is what OBT-547's approval hook stands on.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db.models.resource_request import RRRequest, RRRequestLink
from app.services.common import tokens
from scripts.seed_apps_roles import seeded_roles
from tests.baker import make_app, make_role, make_user
from tests.resource_request_harness import REQUESTS, draft
from tests.test_resource_requests.conftest import auth_header, grant, make_membership

LINKS = "/api/resource-requests/links"


@pytest.fixture()
async def shema_app(db_session):
    app = await make_app(db_session, app_key="shema", name="Shemá", auto_approve=False)
    for role_key, label in seeded_roles("shema"):
        await make_role(db_session, app.id, role_key=role_key, label=label, is_system=True)
    return app


async def platform_admin(db_session, email: str = "admin@links.test"):
    user = await make_user(db_session, email=email, is_platform_admin=True)
    return user, await auth_header(db_session, user)


async def issue(client, headers, email: str = "Equipe@Fora.org", hint: str = "equipe X"):
    return await client.post(LINKS, json={"email": email, "project_hint": hint}, headers=headers)


# ——— who issues —————————————————————————————————————————————————————————————————


async def test_the_admin_issues_a_link_and_gets_its_token_and_code_once(
    db_session, client, rrf_app, shema_app
) -> None:
    admin, headers = await platform_admin(db_session)

    res = await issue(client, headers)

    assert res.status_code == 201, res.text
    body = res.json()
    assert body["email"] == "equipe@fora.org"
    assert body["project_hint"] == "equipe X"
    assert body["status"] == "pending"
    assert body["created_by"] == admin.id
    assert len(body["code"]) == 6 and body["code"].isdigit()

    row = await db_session.get(RRRequestLink, body["id"])
    assert row.token_hash == tokens.digest(body["token"])
    assert row.code_hash == tokens.digest(body["code"])
    assert body["token"] not in (row.token_hash, row.code_hash)


async def test_the_link_lives_sixty_days(db_session, client, rrf_app, shema_app) -> None:
    _admin, headers = await platform_admin(db_session)
    before = datetime.now(UTC)

    body = (await issue(client, headers)).json()

    expires = datetime.fromisoformat(body["expires_at"])
    assert expires.tzinfo is not None, "a link's expiry travels with its offset"
    assert timedelta(days=59) < expires - before <= timedelta(days=60, minutes=1)


@pytest.mark.parametrize("app_name", ["rrf_app", "shema_app"])
async def test_admin_in_either_app_issues(
    db_session, client, rrf_app, shema_app, app_name: str
) -> None:
    """The Admin of OBT-522 is one role seeded in both apps — and both fixtures carry it, since
    ``rrf_app`` reads ``seeded_roles`` (OBT-568); this test used to write the form's row itself."""
    app = {"rrf_app": rrf_app, "shema_app": shema_app}[app_name]
    user = await make_user(db_session, email=f"admin-{app_name}@links.test")
    await grant(db_session, user, app, "admin")

    res = await issue(client, await auth_header(db_session, user))

    assert res.status_code == 201, res.text


@pytest.mark.parametrize("who", ["mesa", "gestor", "member", "nobody"])
async def test_nobody_else_issues_lists_or_revokes(
    db_session, client, rrf_app, shema_app, who: str
) -> None:
    _admin, admin_h = await platform_admin(db_session)
    link_id = (await issue(client, admin_h)).json()["id"]
    user = await make_user(db_session, email=f"{who}@links.test")
    if who in ("mesa", "gestor"):
        await grant(db_session, user, rrf_app, who)
    elif who == "member":
        await make_membership(db_session, user, "kadiweu")
    headers = await auth_header(db_session, user)

    issued = await issue(client, headers)
    listed = await client.get(LINKS, headers=headers)
    revoked = await client.post(f"{LINKS}/{link_id}/revoke", headers=headers)

    assert (issued.status_code, listed.status_code, revoked.status_code) == (403, 403, 403)
    assert (await db_session.get(RRRequestLink, link_id)).revoked_at is None


async def test_no_session_is_refused(client, rrf_app, shema_app) -> None:
    assert (await client.post(LINKS, json={"email": "a@b.org"})).status_code == 401
    assert (await client.get(LINKS)).status_code == 401


@pytest.mark.parametrize(
    "body",
    [{"email": "sem-arroba"}, {"email": "a@b.org", "token": "x"}, {"project_hint": "x"}],
)
async def test_a_malformed_issue_is_422(db_session, client, rrf_app, shema_app, body) -> None:
    _admin, headers = await platform_admin(db_session)

    assert (await client.post(LINKS, json=body, headers=headers)).status_code == 422


# ——— the list and the states ————————————————————————————————————————————————————


async def test_the_list_shows_every_state_and_never_a_secret(
    db_session, client, rrf_app, shema_app
) -> None:
    _admin, headers = await platform_admin(db_session)
    ids = [(await issue(client, headers, email=f"{n}@fora.org")).json()["id"] for n in range(4)]
    verified = await db_session.get(RRRequestLink, ids[1])
    expired = await db_session.get(RRRequestLink, ids[2])
    verified.verified_at = datetime.now(UTC)
    expired.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    await db_session.commit()
    await client.post(f"{LINKS}/{ids[3]}/revoke", headers=headers)

    listed = {row["id"]: row for row in (await client.get(LINKS, headers=headers)).json()}

    assert [listed[i]["status"] for i in ids] == ["pending", "verified", "expired", "revoked"]
    for row in listed.values():
        assert not {"token", "code", "token_hash", "code_hash", "code_attempts"} & set(row)


async def test_revoking_is_idempotent_and_keeps_the_first_moment(
    db_session, client, rrf_app, shema_app
) -> None:
    _admin, headers = await platform_admin(db_session)
    link_id = (await issue(client, headers)).json()["id"]

    first = (await client.post(f"{LINKS}/{link_id}/revoke", headers=headers)).json()
    second = await client.post(f"{LINKS}/{link_id}/revoke", headers=headers)

    assert first["status"] == "revoked"
    assert second.status_code == 200
    assert second.json()["revoked_at"] == first["revoked_at"]


async def test_revoking_an_unknown_link_is_404(db_session, client, rrf_app, shema_app) -> None:
    _admin, headers = await platform_admin(db_session)

    assert (await client.post(f"{LINKS}/nao-existe/revoke", headers=headers)).status_code == 404


# ——— the schema OBT-547 stands on ————————————————————————————————————————————————


async def test_a_request_opened_today_carries_no_link(db_session, client, rrf_app) -> None:
    """The columns arrive empty: nothing that opens a request today writes them."""
    user = await make_user(db_session, email="membro@links.test")
    await make_membership(db_session, user, "kadiweu")

    created = await client.post(REQUESTS, json=draft(), headers=await auth_header(db_session, user))

    row = await db_session.get(RRRequest, created.json()["id"])
    assert row.request_link_id is None
    assert row.started_by_link_id is None


async def test_one_open_instance_per_link(db_session, client, rrf_app, shema_app) -> None:
    """BE-25's lock, with the link as the team — held by the index, written straight to it."""
    admin, headers = await platform_admin(db_session)
    link_id = (await issue(client, headers)).json()["id"]
    for _ in range(2):
        db_session.add(
            RRRequest(
                request_type="traducao",
                created_by=admin.id,
                request_link_id=link_id,
                started_by_link_id=link_id,
            )
        )

    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


async def test_a_submitted_link_request_frees_the_link(
    db_session, client, rrf_app, shema_app
) -> None:
    admin, headers = await platform_admin(db_session)
    link_id = (await issue(client, headers)).json()["id"]
    db_session.add(
        RRRequest(
            request_type="traducao",
            created_by=admin.id,
            request_link_id=link_id,
            submitted_at=datetime.now(UTC),
        )
    )
    db_session.add(RRRequest(request_type="traducao", created_by=admin.id, request_link_id=link_id))
    await db_session.commit()

    rows = await db_session.execute(select(RRRequest).where(RRRequest.request_link_id == link_id))
    assert len(rows.scalars().all()) == 2


def test_the_migration_writes_the_index_the_model_declares() -> None:
    import importlib.util
    from pathlib import Path

    revision = Path(__file__).parents[2] / "alembic" / "versions" / "20260929_rr10_request_links.py"
    spec = importlib.util.spec_from_file_location("_rr10", revision)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    index = next(
        index
        for index in RRRequest.__table__.indexes
        if index.name == "uq_rr_requests_one_open_per_link"
    )
    assert index.unique
    assert [column.name for column in index.columns] == ["request_link_id"]
    for dialect in ("postgresql", "sqlite"):
        assert str(index.dialect_options[dialect]["where"]) == migration.OPEN
