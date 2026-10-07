"""The Admin invites somebody with no account — OBT-543's fourth line, end to end.

An invitation to a Shemá regional role carries its regions; the person signs up with the
invited address and accepts on the form's route, which is generic by token; the role **and**
the regions land in one commit, authored by whoever invited. Around that: the link lands on
the PME's ``/convite`` page for every role, the letter is BE-12's template, ``admin`` is not
granted by link, a week-old invitation cannot rewrite a newer scope or hand back a revoked
role, and the two service packages import each other in a way that holds in either order.
"""

from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from sqlalchemy import select, update

from app.api.shema._deps import APP_KEY, FORM_APP_KEY
from app.core.config import get_settings
from app.db.models.auth import AccessInvite, App, Role, UserAppRole
from app.db.models.shema_enums import ShemaRegionKey
from app.db.models.shema_region import ShemaUserRegion
from app.services.shema import set_region_scope
from tests.email_harness import client_class
from tests.shema_admin_harness import (
    CHANGES,
    FORM_INVITES,
    GRANTS,
    INVITES,
    PME_URL,
    REVOKE,
    WITHDRAW,
    give_urls,
    make_account,
    make_admin,
    surface_client,
)
from tests.test_shema.conftest import SESSION, auth_header

REPO = Path(__file__).resolve().parents[2]


def _invite(email: str, role: str, app: str = APP_KEY, regions: list[str] | None = None):
    body: dict[str, object] = {"email": email, "appKey": app, "roleKey": role}
    if regions is not None:
        body["regionKeys"] = regions
    return body


def _token(body: dict) -> str:
    return body["inviteUrl"].split("token=")[1]


async def _live_roles(db_session, user_id: str) -> list[tuple[str, str]]:
    stmt = (
        select(App.app_key, Role.role_key)
        .join(Role, Role.app_id == App.id)
        .join(UserAppRole, UserAppRole.role_id == Role.id)
        .where(UserAppRole.user_id == user_id, UserAppRole.revoked_at.is_(None))
    )
    return sorted((await db_session.execute(stmt)).tuples().all())


async def _signup(client, email: str) -> tuple[str, dict[str, str]]:
    res = await client.post(
        "/api/auth/signup",
        json={"email": email, "password": "a-long-password", "display_name": "Joiner"},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    return body["user"]["id"], {"Authorization": f"Bearer {body['tokens']['access_token']}"}


# --- the DoD's case ------------------------------------------------------------------------


async def test_an_invite_accepted_after_signup_applies_the_role_and_the_regions(
    db_session, shema_app, form_app
) -> None:
    """Invite ``coordinator`` with two regions → sign up with that address → accept.

    The role is held, the regions are the account's scope with the inviter as their author,
    the person's own session answers both, and the history names the inviter for the grant.
    """
    await give_urls(db_session, shema_app, form_app)
    admin, headers = await make_admin(db_session, shema_app, form_app)

    async with surface_client(db_session) as client:
        sent = await client.post(
            INVITES,
            json=_invite("joiner@shema.example", "coordinator", regions=["africa", "europe"]),
            headers=headers,
        )
        assert sent.status_code == 201, sent.text
        joiner_id, joiner = await _signup(client, "joiner@shema.example")
        accepted = await client.post(f"{FORM_INVITES}/{_token(sent.json())}/accept", headers=joiner)
        session = await client.get(SESSION, headers=joiner)
        changes = await client.get(CHANGES, headers=headers)

    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["granted_by"] == admin.id
    assert await _live_roles(db_session, joiner_id) == [(APP_KEY, "coordinator")]
    rows = await db_session.execute(
        select(ShemaUserRegion.region_key, ShemaUserRegion.granted_by).where(
            ShemaUserRegion.user_id == joiner_id
        )
    )
    assert sorted((key.value, by) for key, by in rows.all()) == [
        ("africa", admin.id),
        ("europe", admin.id),
    ]
    assert session.json()["roles"] == ["coordinator"]
    assert session.json()["regionScope"] == ["africa", "europe"]
    grants = [e for e in changes.json() if e["userId"] == joiner_id and e["roleKey"]]
    assert [(e["action"], e["roleKey"], e["actorId"]) for e in grants] == [
        ("granted", "coordinator", admin.id)
    ]


async def test_every_invite_links_to_the_pmes_page_and_leaves_through_the_template(
    db_session, shema_app, form_app, monkeypatch
) -> None:
    """A mesa's invitation too: the form has no sign-in since 22/set, so the link is the
    PME's ``/convite`` and the letter is named after the PME — never the form's address."""
    await give_urls(db_session, shema_app, form_app)
    _admin, headers = await make_admin(db_session, shema_app, form_app)

    async with surface_client(db_session) as client:
        settings = get_settings()
        monkeypatch.setattr(settings, "email_provider", "resend")
        monkeypatch.setattr(settings, "resend_api_key", "test-key")
        recorded: list = []
        monkeypatch.setattr(httpx, "AsyncClient", client_class(recorded))
        sent = await client.post(
            INVITES, json=_invite("seat@shema.example", "mesa", FORM_APP_KEY), headers=headers
        )

    assert sent.status_code == 201, sent.text
    body = sent.json()
    assert body["inviteUrl"].startswith(f"{PME_URL}/convite?token=")
    assert body["emailSent"] is True
    assert body["appKey"] == FORM_APP_KEY
    [(url, kwargs)] = recorded
    assert url == "https://api.resend.com/emails"
    assert kwargs["json"]["to"] == ["seat@shema.example"]
    assert body["inviteUrl"] in kwargs["json"]["html"]
    assert kwargs["json"]["subject"] == "You're invited to Shemá"


async def test_the_lookup_says_which_regions_the_invite_gives(
    db_session, shema_app, form_app
) -> None:
    """The form's anonymous lookup, which the PME's ``/convite`` page reads before sign-up."""
    _admin, headers = await make_admin(db_session, shema_app, form_app)

    async with surface_client(db_session) as client:
        sent = await client.post(
            INVITES,
            json=_invite("joiner@shema.example", "obtLab", regions=["asia"]),
            headers=headers,
        )
        lookup = await client.get(f"{FORM_INVITES}/{_token(sent.json())}")

    assert lookup.status_code == 200
    assert lookup.json()["region_keys"] == ["asia"]
    assert lookup.json()["role_key"] == "obtLab"
    assert lookup.json()["account_exists"] is False


# --- what an invitation may not do -----------------------------------------------------------


async def test_the_admin_role_is_not_granted_by_link(db_session, shema_app, form_app) -> None:
    _admin, headers = await make_admin(db_session, shema_app, form_app)

    async with surface_client(db_session) as client:
        res = await client.post(
            INVITES, json=_invite("new@shema.example", "admin"), headers=headers
        )

    assert res.status_code == 422
    assert "never through a link" in res.json()["detail"]
    assert (await db_session.execute(select(AccessInvite.id))).all() == []


async def test_a_regional_invite_without_regions_is_refused(
    db_session, shema_app, form_app
) -> None:
    _admin, headers = await make_admin(db_session, shema_app, form_app)

    async with surface_client(db_session) as client:
        res = await client.post(
            INVITES, json=_invite("new@shema.example", "resourceCircle"), headers=headers
        )

    assert res.status_code == 422
    assert (await db_session.execute(select(AccessInvite.id))).all() == []


async def test_inviting_yourself_is_refused(db_session, shema_app, form_app) -> None:
    admin, headers = await make_admin(db_session, shema_app, form_app)

    async with surface_client(db_session) as client:
        res = await client.post(
            INVITES, json=_invite(admin.email, "coordinator", regions=["africa"]), headers=headers
        )

    assert res.status_code == 400
    assert res.json()["detail"] == "You cannot invite yourself."


async def test_a_second_pending_invite_is_refused(db_session, shema_app, form_app) -> None:
    _admin, headers = await make_admin(db_session, shema_app, form_app)

    async with surface_client(db_session) as client:
        first = await client.post(
            INVITES,
            json=_invite("new@shema.example", "coordinator", regions=["africa"]),
            headers=headers,
        )
        second = await client.post(
            INVITES,
            json=_invite("new@shema.example", "coordinator", regions=["africa"]),
            headers=headers,
        )

    assert first.status_code == 201
    assert second.status_code == 409


async def test_accepting_is_refused_when_it_would_change_a_regional_scope(
    db_session, shema_app, form_app
) -> None:
    """Written for somebody with no account, accepted by somebody an Admin has since given a
    regional scope: the link does not rewrite the newer decision. The same scope is fine."""
    _admin, headers = await make_admin(db_session, shema_app, form_app)

    async with surface_client(db_session) as client:
        other = await client.post(
            INVITES,
            json=_invite("joiner@shema.example", "obtLab", regions=["asia"]),
            headers=headers,
        )
        same = await client.post(
            INVITES,
            json=_invite("joiner@shema.example", "resourceCircle", regions=["africa"]),
            headers=headers,
        )
        joiner_id, joiner = await _signup(client, "joiner@shema.example")
        await client.post(
            GRANTS,
            json={
                "userId": joiner_id,
                "appKey": APP_KEY,
                "roleKey": "coordinator",
                "regionKeys": ["africa"],
            },
            headers=headers,
        )
        refused = await client.post(f"{FORM_INVITES}/{_token(other.json())}/accept", headers=joiner)
        accepted = await client.post(f"{FORM_INVITES}/{_token(same.json())}/accept", headers=joiner)

    assert refused.status_code == 409
    assert "region scope" in refused.json()["detail"]
    assert accepted.status_code == 200, accepted.text
    assert await _live_roles(db_session, joiner_id) == [
        (APP_KEY, "coordinator"),
        (APP_KEY, "resourceCircle"),
    ]


async def test_a_direct_revoke_recalls_the_pending_invite(db_session, shema_app, form_app) -> None:
    """A week-old link must not hand back a role that was just taken away."""
    _admin, headers = await make_admin(db_session, shema_app, form_app)
    person = await make_account(db_session, "person@shema.example", (form_app, "mesa"))

    async with surface_client(db_session) as client:
        sent = await client.post(
            INVITES, json=_invite(person.email, "mesa", FORM_APP_KEY), headers=headers
        )
        await client.post(
            REVOKE,
            json={"userId": person.id, "appKey": FORM_APP_KEY, "roleKey": "mesa"},
            headers=headers,
        )
        accept = await client.post(
            f"{FORM_INVITES}/{_token(sent.json())}/accept",
            headers=await auth_header(db_session, person),
        )

    assert accept.status_code == 409
    assert "revoked" in accept.json()["detail"]
    assert await _live_roles(db_session, person.id) == []


# --- the list and the recall ---------------------------------------------------------------------


async def test_open_invites_are_listed_newest_first_with_their_regions(
    db_session, shema_app, form_app
) -> None:
    _admin, headers = await make_admin(db_session, shema_app, form_app)

    async with surface_client(db_session) as client:
        older = await client.post(
            INVITES, json=_invite("a@shema.example", "gestor", FORM_APP_KEY), headers=headers
        )
        # SQLite stamps ``created_at`` to the second; a minute apart, the order is the point.
        await db_session.execute(
            update(AccessInvite)
            .where(AccessInvite.id == older.json()["id"])
            .values(created_at=datetime.now(UTC) - timedelta(minutes=1))
        )
        await db_session.commit()
        await client.post(
            INVITES,
            json=_invite("b@shema.example", "coordinator", regions=["oceania"]),
            headers=headers,
        )
        listed = await client.get(INVITES, headers=headers)

    assert listed.status_code == 200
    body = listed.json()
    assert [(e["email"], e["appKey"], e["regionKeys"]) for e in body] == [
        ("b@shema.example", APP_KEY, ["oceania"]),
        ("a@shema.example", FORM_APP_KEY, []),
    ]
    assert {e["status"] for e in body} == {"pending"}
    assert all("inviteUrl" not in e for e in body)


async def test_a_withdrawn_invite_cannot_be_accepted(db_session, shema_app, form_app) -> None:
    _admin, headers = await make_admin(db_session, shema_app, form_app)

    async with surface_client(db_session) as client:
        sent = await client.post(
            INVITES,
            json=_invite("joiner@shema.example", "coordinator", regions=["africa"]),
            headers=headers,
        )
        withdrawn = await client.post(
            WITHDRAW, json={"inviteId": sent.json()["id"]}, headers=headers
        )
        again = await client.post(WITHDRAW, json={"inviteId": sent.json()["id"]}, headers=headers)
        _joiner_id, joiner = await _signup(client, "joiner@shema.example")
        accept = await client.post(f"{FORM_INVITES}/{_token(sent.json())}/accept", headers=joiner)

    assert withdrawn.status_code == 200
    assert withdrawn.json()["status"] == "revoked"
    assert again.status_code == 200
    assert accept.status_code == 409


async def test_an_invite_of_another_app_is_not_found(db_session, shema_app, form_app) -> None:
    """The surface recalls the two apps' invitations and cannot even confirm another's."""
    from app.services.resource_request_access.invite_store import issue_invite
    from tests.baker import make_app, make_role, make_user

    other = await make_app(db_session, app_key="oral-collector", name="Oral Collector")
    await make_role(db_session, other.id, role_key="member", label="Member")
    installation = await make_user(
        db_session, email="installation@shema.example", is_platform_admin=True
    )
    issued = await issue_invite(
        db_session, installation, "oral-collector", "x@shema.example", "member"
    )
    _admin, headers = await make_admin(db_session, shema_app, form_app)

    async with surface_client(db_session) as client:
        res = await client.post(WITHDRAW, json={"inviteId": issued.invite.id}, headers=headers)

    assert res.status_code == 404
    assert issued.invite.revoked_at is None


async def test_an_accepted_invite_is_past_withdrawing(db_session, shema_app, form_app) -> None:
    _admin, headers = await make_admin(db_session, shema_app, form_app)

    async with surface_client(db_session) as client:
        sent = await client.post(
            INVITES,
            json=_invite("joiner@shema.example", "coordinator", regions=["africa"]),
            headers=headers,
        )
        _joiner_id, joiner = await _signup(client, "joiner@shema.example")
        await client.post(f"{FORM_INVITES}/{_token(sent.json())}/accept", headers=joiner)
        res = await client.post(WITHDRAW, json={"inviteId": sent.json()["id"]}, headers=headers)

    assert res.status_code == 409


async def test_an_accepted_invite_reads_in_changes_as_the_inviters_grant(
    db_session, shema_app, form_app
) -> None:
    """The concession was the inviter's, whenever the click came."""
    admin, headers = await make_admin(db_session, shema_app, form_app)

    async with surface_client(db_session) as client:
        sent = await client.post(
            INVITES, json=_invite("joiner@shema.example", "gestor", FORM_APP_KEY), headers=headers
        )
        joiner_id, joiner = await _signup(client, "joiner@shema.example")
        await client.post(f"{FORM_INVITES}/{_token(sent.json())}/accept", headers=joiner)
        changes = await client.get(CHANGES, headers=headers)

    [entry] = [e for e in changes.json() if e["userId"] == joiner_id]
    assert (entry["action"], entry["appKey"], entry["roleKey"]) == (
        "granted",
        FORM_APP_KEY,
        "gestor",
    )
    assert entry["actorId"] == admin.id
    assert entry["userEmail"] == "joiner@shema.example"


async def test_a_regional_scope_kept_by_an_operator_is_left_to_the_invite_with_no_role(
    db_session, shema_app, form_app
) -> None:
    """Rows left under no regional role reach nothing, so an invite replaces them freely."""
    _admin, headers = await make_admin(db_session, shema_app, form_app)

    async with surface_client(db_session) as client:
        sent = await client.post(
            INVITES,
            json=_invite("joiner@shema.example", "coordinator", regions=["asia"]),
            headers=headers,
        )
        joiner_id, joiner = await _signup(client, "joiner@shema.example")
        await set_region_scope(db_session, joiner_id, [ShemaRegionKey.EUROPE])
        accepted = await client.post(f"{FORM_INVITES}/{_token(sent.json())}/accept", headers=joiner)

    assert accepted.status_code == 200, accepted.text
    rows = await db_session.execute(
        select(ShemaUserRegion.region_key).where(ShemaUserRegion.user_id == joiner_id)
    )
    assert [key.value for key in rows.scalars()] == ["asia"]


# --- the two packages -------------------------------------------------------------------------


def _imports(relative: str) -> set[tuple[str, str]]:
    tree = ast.parse((REPO / relative).read_text(encoding="utf-8"))
    return {
        (node.module or "", alias.name)
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }


def test_the_two_packages_import_each_other_by_submodule() -> None:
    """The Shemá services and the form's invite package import each other, and only the
    submodule spelling binds a function in either order: ``from app.services.shema import
    x`` run while that package is half-imported binds the *module* ``x`` and fails at the
    first call, in production's order and not in the suite's."""
    accept = _imports("app/services/resource_request_access/accept_invite.py")
    assert ("app.services.shema.apply_invited_scope", "apply_invited_scope") in accept
    assert not {entry for entry in accept if entry[0] == "app.services.shema"}

    for service in ("grant_role", "revoke_grant", "send_invite", "withdraw_invite", "list_invites"):
        reached = _imports(f"app/services/shema/{service}.py")
        assert not {
            entry for entry in reached if entry[0] == "app.services.resource_request_access"
        }
