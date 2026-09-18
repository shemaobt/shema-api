from sqlalchemy import select

from app.db.models.project import ProjectInvite
from app.services.oral_collector import invite_service
from tests.baker import make_language, make_project, make_user


async def test_create_invite_is_idempotent_for_pending(db_session) -> None:
    lang = await make_language(db_session, code="kos")
    project = await make_project(db_session, lang.id)
    inviter = await make_user(db_session, email="inviter@example.com")
    invitee = await make_user(db_session, email="invitee@example.com")

    first = await invite_service.create_invite(
        db_session, project.id, invitee.email, "member", str(inviter.id)
    )
    original_created_at = first.created_at

    second = await invite_service.create_invite(
        db_session, project.id, invitee.email, "manager", str(inviter.id)
    )

    assert second.id == first.id
    assert second.role == "manager"
    assert second.created_at >= original_created_at

    stmt = select(ProjectInvite).where(
        ProjectInvite.project_id == project.id,
        ProjectInvite.email == invitee.email,
        ProjectInvite.status == "pending",
    )
    rows = (await db_session.execute(stmt)).scalars().all()
    assert len(rows) == 1


async def test_create_invite_reflects_latest_inviter(db_session) -> None:
    lang = await make_language(db_session, code="kos")
    project = await make_project(db_session, lang.id)
    inviter_a = await make_user(db_session, email="a@example.com")
    inviter_b = await make_user(db_session, email="b@example.com")
    invitee = await make_user(db_session, email="invitee@example.com")

    await invite_service.create_invite(
        db_session, project.id, invitee.email, "member", str(inviter_a.id)
    )
    second = await invite_service.create_invite(
        db_session, project.id, invitee.email, "member", str(inviter_b.id)
    )

    assert second.invited_by == str(inviter_b.id)


async def test_list_user_invites_returns_project_name(db_session) -> None:
    lang = await make_language(db_session, code="kos")
    project = await make_project(db_session, lang.id, name="Kokama Bible")
    inviter = await make_user(db_session, email="inviter@example.com")
    invitee = await make_user(db_session, email="invitee@example.com")

    await invite_service.create_invite(
        db_session, project.id, invitee.email, "member", str(inviter.id)
    )

    rows = await invite_service.list_user_invites(db_session, invitee.email)
    assert len(rows) == 1
    invite, project_name = rows[0]
    assert invite.project_id == project.id
    assert project_name == "Kokama Bible"


async def test_accept_invite_is_idempotent_when_access_exists(db_session) -> None:
    from sqlalchemy import select

    from app.db.models.project import ProjectUserAccess

    lang = await make_language(db_session, code="kos")
    project = await make_project(db_session, lang.id)
    inviter = await make_user(db_session, email="inviter@example.com")
    invitee = await make_user(db_session, email="invitee@example.com")

    invite = await invite_service.create_invite(
        db_session, project.id, invitee.email, "member", str(inviter.id)
    )

    db_session.add(ProjectUserAccess(project_id=project.id, user_id=str(invitee.id), role="member"))
    await db_session.commit()

    accepted = await invite_service.accept_invite(
        db_session, invite.id, str(invitee.id), invitee.email
    )
    assert accepted.status == "accepted"

    stmt = select(ProjectUserAccess).where(
        ProjectUserAccess.project_id == project.id,
        ProjectUserAccess.user_id == str(invitee.id),
    )
    rows = (await db_session.execute(stmt)).scalars().all()
    assert len(rows) == 1


async def test_accept_invite_grants_access_and_marks_accepted(db_session) -> None:
    from sqlalchemy import select

    from app.db.models.project import ProjectUserAccess

    lang = await make_language(db_session, code="kos")
    project = await make_project(db_session, lang.id)
    inviter = await make_user(db_session, email="inviter@example.com")
    invitee = await make_user(db_session, email="invitee@example.com")

    invite = await invite_service.create_invite(
        db_session, project.id, invitee.email, "manager", str(inviter.id)
    )

    accepted = await invite_service.accept_invite(
        db_session, invite.id, str(invitee.id), invitee.email
    )
    assert accepted.status == "accepted"
    assert accepted.accepted_at is not None

    stmt = select(ProjectUserAccess).where(
        ProjectUserAccess.project_id == project.id,
        ProjectUserAccess.user_id == str(invitee.id),
    )
    access = (await db_session.execute(stmt)).scalar_one()
    assert access.role == "manager"
