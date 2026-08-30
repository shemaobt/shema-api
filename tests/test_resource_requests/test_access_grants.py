"""Naming a user into a privileged role — the client's asymmetric rule, verbatim.

Admin and Gestor concede, only Admin revokes (answer of 28/08, "os dois" /
asymmetry intended). What is tested here is the naming door: who may push each
verb, that both refuse self-service, that mesa and gestor exclude each other
while equipe accumulates, and that every write says who and when — including
``revoked_by``, which the shared revoke path never recorded.
"""

from __future__ import annotations

from sqlalchemy import select

from app.db.models.auth import UserAppRole
from tests.baker import make_user
from tests.test_resource_requests.conftest import auth_header, grant

ACCESS = "/api/resource-requests/access"


async def _actor(db_session, rrf_app, role_key: str | None, email: str):
    """A user, optionally holding one of the app's roles, plus their auth header."""
    user = await make_user(db_session, email=email, is_platform_admin=role_key == "admin")
    if role_key and role_key != "admin":
        await grant(db_session, user, rrf_app, role_key)
    return user, await auth_header(db_session, user)


async def test_a_gestor_grants_equipe_and_the_grant_names_its_author(
    db_session, client, rrf_app
) -> None:
    gestor, headers = await _actor(db_session, rrf_app, "gestor", "gestor@rrf.test")
    target = await make_user(db_session, email="new-equipe@rrf.test")

    res = await client.post(
        f"{ACCESS}/grants",
        json={"target_user_id": target.id, "role_key": "equipe"},
        headers=headers,
    )

    assert res.status_code == 200
    body = res.json()
    assert body["user_id"] == target.id
    assert body["role_key"] == "equipe"
    assert body["granted_by"] == gestor.id
    assert body["revoked_at"] is None


async def test_a_platform_admin_grants_without_holding_any_role_here(
    db_session, client, rrf_app
) -> None:
    _admin, headers = await _actor(db_session, rrf_app, "admin", "padmin@rrf.test")
    target = await make_user(db_session, email="named-mesa@rrf.test")

    res = await client.post(
        f"{ACCESS}/grants",
        json={"target_user_id": target.id, "role_key": "mesa"},
        headers=headers,
    )

    assert res.status_code == 200
    assert res.json()["role_key"] == "mesa"


async def test_equipe_and_mesa_cannot_grant(db_session, client, rrf_app) -> None:
    target = await make_user(db_session, email="wanted@rrf.test")
    for role_key in ("equipe", "mesa"):
        _actor_user, headers = await _actor(
            db_session, rrf_app, role_key, f"{role_key}-actor@rrf.test"
        )

        res = await client.post(
            f"{ACCESS}/grants",
            json={"target_user_id": target.id, "role_key": "equipe"},
            headers=headers,
        )

        assert res.status_code == 403


async def test_the_gestor_who_concedes_cannot_revoke(db_session, client, rrf_app) -> None:
    """The asymmetry is the answer, not an oversight."""
    _gestor, headers = await _actor(db_session, rrf_app, "gestor", "gestor2@rrf.test")
    target = await make_user(db_session, email="held@rrf.test")
    await grant(db_session, target, rrf_app, "equipe")

    res = await client.post(
        f"{ACCESS}/grants/revoke",
        json={"target_user_id": target.id, "role_key": "equipe"},
        headers=headers,
    )

    assert res.status_code == 403


async def test_an_admin_revokes_and_the_revocation_names_its_author(
    db_session, client, rrf_app
) -> None:
    admin, headers = await _actor(db_session, rrf_app, "admin", "padmin2@rrf.test")
    target = await make_user(db_session, email="leaving@rrf.test")
    await grant(db_session, target, rrf_app, "mesa")

    res = await client.post(
        f"{ACCESS}/grants/revoke",
        json={"target_user_id": target.id, "role_key": "mesa"},
        headers=headers,
    )

    assert res.status_code == 200
    body = res.json()
    assert body["revoked_at"] is not None
    assert body["revoked_by"] == admin.id

    row = (
        await db_session.execute(select(UserAppRole).where(UserAppRole.user_id == target.id))
    ).scalar_one()
    assert row.revoked_at is not None
    assert row.revoked_by == admin.id


async def test_mesa_and_gestor_exclude_each_other_both_ways(db_session, client, rrf_app) -> None:
    _admin, headers = await _actor(db_session, rrf_app, "admin", "padmin3@rrf.test")
    holds_mesa = await make_user(db_session, email="holds-mesa@rrf.test")
    await grant(db_session, holds_mesa, rrf_app, "mesa")
    holds_gestor = await make_user(db_session, email="holds-gestor@rrf.test")
    await grant(db_session, holds_gestor, rrf_app, "gestor")

    to_gestor = await client.post(
        f"{ACCESS}/grants",
        json={"target_user_id": holds_mesa.id, "role_key": "gestor"},
        headers=headers,
    )
    to_mesa = await client.post(
        f"{ACCESS}/grants",
        json={"target_user_id": holds_gestor.id, "role_key": "mesa"},
        headers=headers,
    )

    assert to_gestor.status_code == 409
    assert to_mesa.status_code == 409


async def test_equipe_is_the_floor_and_accumulates(db_session, client, rrf_app) -> None:
    _admin, headers = await _actor(db_session, rrf_app, "admin", "padmin4@rrf.test")
    target = await make_user(db_session, email="stacking@rrf.test")
    await grant(db_session, target, rrf_app, "gestor")

    res = await client.post(
        f"{ACCESS}/grants",
        json={"target_user_id": target.id, "role_key": "equipe"},
        headers=headers,
    )

    assert res.status_code == 200


async def test_self_grant_is_refused_on_both_verbs_even_for_the_admin(
    db_session, client, rrf_app
) -> None:
    admin, admin_headers = await _actor(db_session, rrf_app, "admin", "padmin5@rrf.test")
    gestor, gestor_headers = await _actor(db_session, rrf_app, "gestor", "gestor3@rrf.test")

    self_grant_admin = await client.post(
        f"{ACCESS}/grants",
        json={"target_user_id": admin.id, "role_key": "equipe"},
        headers=admin_headers,
    )
    self_grant_gestor = await client.post(
        f"{ACCESS}/grants",
        json={"target_user_id": gestor.id, "role_key": "mesa"},
        headers=gestor_headers,
    )
    self_revoke_admin = await client.post(
        f"{ACCESS}/grants/revoke",
        json={"target_user_id": admin.id, "role_key": "equipe"},
        headers=admin_headers,
    )

    assert self_grant_admin.status_code == 400
    assert self_grant_gestor.status_code == 400
    assert self_revoke_admin.status_code == 400


async def test_granting_to_a_user_that_does_not_exist_is_a_422(
    db_session, client, rrf_app
) -> None:
    _admin, headers = await _actor(db_session, rrf_app, "admin", "padmin6@rrf.test")

    res = await client.post(
        f"{ACCESS}/grants",
        json={"target_user_id": "no-such-user", "role_key": "equipe"},
        headers=headers,
    )

    assert res.status_code == 422


async def test_the_overview_is_visible_to_those_who_concede_and_hidden_below(
    db_session, client, rrf_app
) -> None:
    """FE-30's screen: gestor and admin read it; equipe is refused."""
    gestor, gestor_headers = await _actor(db_session, rrf_app, "gestor", "gestor4@rrf.test")
    _equipe, equipe_headers = await _actor(db_session, rrf_app, "equipe", "equipe2@rrf.test")

    seen = await client.get(ACCESS, headers=gestor_headers)
    refused = await client.get(ACCESS, headers=equipe_headers)

    assert seen.status_code == 200
    granted = {(g["email"], g["role_key"]) for g in seen.json()["grants"]}
    assert ("gestor4@rrf.test", "gestor") in granted
    assert ("equipe2@rrf.test", "equipe") in granted
    assert refused.status_code == 403
