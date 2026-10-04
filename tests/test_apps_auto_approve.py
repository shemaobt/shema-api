from sqlalchemy import select

from app.db.models.auth import AccessRequest, App, UserAppRole
from app.services.access_request.create_access_request import create_access_request
from app.services.app.create_app import create_app
from app.services.app.update_app import update_app
from app.services.authorization.list_roles import list_roles
from tests.baker import make_access_request, make_role, make_user


async def _seed_th_user_role(db_session):
    th_app = (
        await db_session.execute(select(App).where(App.app_key == "translation-helper"))
    ).scalar_one()
    await make_role(db_session, th_app.id, role_key="user", label="User", is_system=True)
    return th_app


async def test_create_app_defaults_auto_approve_to_false(db_session) -> None:
    new_app = await create_app(db_session, app_key="new-app", name="New App")
    assert new_app.auto_approve is False


async def test_create_app_can_set_auto_approve_true(db_session) -> None:
    new_app = await create_app(db_session, app_key="new-app", name="New App", auto_approve=True)
    assert new_app.auto_approve is True


async def test_create_access_request_stays_pending_when_auto_approve_off(
    db_session,
) -> None:
    """Default behavior: admin still has to review requests manually."""
    await _seed_th_user_role(db_session)
    user = await make_user(db_session, email="aa_a@test.com")

    request = await create_access_request(db_session, user.id, "translation-helper")

    assert request.status == "pending"
    assert request.reviewed_at is None
    roles = await list_roles(db_session, user.id, "translation-helper")
    assert roles == []


async def test_create_access_request_auto_approves_and_grants_role_when_flag_on(
    db_session,
) -> None:
    """auto_approve=True: skip the queue entirely and grant the default role on signup."""
    th_app = await _seed_th_user_role(db_session)
    th_app.auto_approve = True
    await db_session.commit()

    user = await make_user(db_session, email="aa_b@test.com")
    request = await create_access_request(db_session, user.id, "translation-helper")

    assert request.status == "approved"
    assert request.reviewed_at is not None
    assert request.review_reason == "auto-approved"

    roles = await list_roles(db_session, user.id, "translation-helper")
    assert roles == [("translation-helper", "user")]


async def test_create_access_request_idempotent_returns_existing_when_auto_approve_on(
    db_session,
) -> None:
    """Auto-approve must not duplicate UserAppRole rows if a request already exists."""
    th_app = await _seed_th_user_role(db_session)
    th_app.auto_approve = True
    await db_session.commit()

    user = await make_user(db_session, email="aa_c@test.com")

    first = await create_access_request(db_session, user.id, "translation-helper")
    second = await create_access_request(db_session, user.id, "translation-helper")
    assert first.id == second.id

    role_rows = (
        (await db_session.execute(select(UserAppRole).where(UserAppRole.user_id == user.id)))
        .scalars()
        .all()
    )
    assert len(role_rows) == 1


async def test_update_app_turning_auto_approve_on_retroactively_approves_pending(
    db_session,
) -> None:
    """Flipping the toggle ON sweeps the existing pending requests so the admin
    doesn't have to click through them one by one."""
    th_app = await _seed_th_user_role(db_session)
    admin = await make_user(db_session, email="aa_admin@test.com", is_platform_admin=True)

    alice = await make_user(db_session, email="aa_alice@test.com")
    bob = await make_user(db_session, email="aa_bob@test.com")
    await make_access_request(db_session, alice.id, th_app.id)
    await make_access_request(db_session, bob.id, th_app.id)

    await update_app(db_session, th_app.id, auto_approve=True, actor=admin)

    pending_rows = (
        (await db_session.execute(select(AccessRequest).where(AccessRequest.app_id == th_app.id)))
        .scalars()
        .all()
    )
    statuses = {r.status for r in pending_rows}
    assert statuses == {"approved"}
    for r in pending_rows:
        assert r.review_reason == "auto-approved (retroactive)"
        assert r.reviewed_by == admin.id
        assert r.reviewed_at is not None

    assert await list_roles(db_session, alice.id, "translation-helper") == [
        ("translation-helper", "user")
    ]
    assert await list_roles(db_session, bob.id, "translation-helper") == [
        ("translation-helper", "user")
    ]


async def test_update_app_turning_auto_approve_off_is_noop_for_existing_users(
    db_session,
) -> None:
    """Disabling the toggle must not revoke roles that were already granted."""
    th_app = await _seed_th_user_role(db_session)
    th_app.auto_approve = True
    await db_session.commit()

    user = await make_user(db_session, email="aa_d@test.com")
    await create_access_request(db_session, user.id, "translation-helper")
    assert await list_roles(db_session, user.id, "translation-helper") == [
        ("translation-helper", "user")
    ]

    await update_app(db_session, th_app.id, auto_approve=False)

    assert await list_roles(db_session, user.id, "translation-helper") == [
        ("translation-helper", "user")
    ]


async def test_update_app_setting_auto_approve_true_when_already_true_does_not_resweep(
    db_session,
) -> None:
    """If the flag was already on, no retroactive sweep should run (idempotent)."""
    th_app = await _seed_th_user_role(db_session)
    th_app.auto_approve = True
    await db_session.commit()

    # An old, dangling pending row left over from before the flag flipped.
    user = await make_user(db_session, email="aa_e@test.com")
    pending = await make_access_request(db_session, user.id, th_app.id)

    await update_app(db_session, th_app.id, auto_approve=True)

    await db_session.refresh(pending)
    assert pending.status == "pending"


async def test_update_app_other_fields_do_not_trigger_retroactive_sweep(
    db_session,
) -> None:
    """Updating only the name should not touch pending access requests."""
    th_app = await _seed_th_user_role(db_session)
    user = await make_user(db_session, email="aa_f@test.com")
    pending = await make_access_request(db_session, user.id, th_app.id)

    await update_app(db_session, th_app.id, name="Renamed App")

    await db_session.refresh(pending)
    assert pending.status == "pending"
