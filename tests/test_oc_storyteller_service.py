import pytest
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import UploadStatus
from app.core.exceptions import AuthorizationError, NotFoundError, ValidationError
from app.db.models.auth import User
from app.db.models.oc_storyteller import OC_Storyteller
from app.db.models.project import ProjectUserAccess
from app.models.oc_storyteller import StorytellerCreate, StorytellerUpdate
from tests.baker import (
    make_language,
    make_oc_recording,
    make_oc_taxonomy,
    make_project,
    make_user,
)


async def _seed_project_with_manager(db: AsyncSession) -> tuple[str, User]:
    lang = await make_language(db)
    project = await make_project(db, lang.id)
    manager = await make_user(db, email="pm@test.com")
    access = ProjectUserAccess(project_id=project.id, user_id=manager.id, role="manager")
    db.add(access)
    await db.commit()
    return project.id, manager


async def _add_member(db: AsyncSession, project_id: str, email: str) -> User:
    member = await make_user(db, email=email)
    access = ProjectUserAccess(project_id=project_id, user_id=member.id, role="member")
    db.add(access)
    await db.commit()
    return member


def _import_service():
    from app.services.oral_collector import storyteller_service

    return storyteller_service


@pytest.mark.asyncio
async def test_create_storyteller_as_manager(db_session: AsyncSession) -> None:
    ss = _import_service()
    project_id, manager = await _seed_project_with_manager(db_session)

    data = StorytellerCreate(
        name="Ana",
        sex="female",
        age=62,
        location="Alto Xingu",
        external_acceptance_confirmed=True,
    )
    st = await ss.create_storyteller(db_session, project_id, data, manager)

    assert st.id is not None
    assert st.project_id == project_id
    assert st.name == "Ana"
    assert st.sex == "female"
    assert st.age == 62
    assert st.external_acceptance_confirmed is True
    assert st.external_acceptance_confirmed_at is not None
    assert st.external_acceptance_confirmed_by == manager.id
    assert st.created_by_user_id == manager.id


@pytest.mark.asyncio
async def test_create_storyteller_as_member(db_session: AsyncSession) -> None:
    ss = _import_service()
    project_id, _ = await _seed_project_with_manager(db_session)
    member = await _add_member(db_session, project_id, "member@test.com")

    data = StorytellerCreate(name="Ana", sex="female", external_acceptance_confirmed=True)
    st = await ss.create_storyteller(db_session, project_id, data, member)

    assert st.created_by_user_id == member.id
    assert st.external_acceptance_confirmed_by == member.id


@pytest.mark.asyncio
async def test_create_storyteller_non_member_blocked(db_session: AsyncSession) -> None:
    ss = _import_service()
    project_id, _ = await _seed_project_with_manager(db_session)
    outsider = await make_user(db_session, email="outsider@test.com")

    data = StorytellerCreate(name="Ana", sex="female", external_acceptance_confirmed=True)
    with pytest.raises(AuthorizationError):
        await ss.create_storyteller(db_session, project_id, data, outsider)


@pytest.mark.asyncio
async def test_create_storyteller_rejects_unconfirmed_at_schema() -> None:
    with pytest.raises(PydanticValidationError):
        StorytellerCreate(name="Ana", sex="female", external_acceptance_confirmed=False)


@pytest.mark.asyncio
async def test_create_storyteller_service_guards_unconfirmed(
    db_session: AsyncSession,
) -> None:
    ss = _import_service()
    project_id, manager = await _seed_project_with_manager(db_session)

    data = StorytellerCreate.model_construct(
        name="Ana",
        sex="female",
        age=None,
        location=None,
        dialect=None,
        external_acceptance_confirmed=False,
    )
    with pytest.raises(ValidationError):
        await ss.create_storyteller(db_session, project_id, data, manager)


@pytest.mark.asyncio
async def test_list_project_storytellers_ordered_by_name(
    db_session: AsyncSession,
) -> None:
    ss = _import_service()
    project_id, manager = await _seed_project_with_manager(db_session)

    for name in ["Zelda", "Ana", "Marcos"]:
        await ss.create_storyteller(
            db_session,
            project_id,
            StorytellerCreate(name=name, sex="female", external_acceptance_confirmed=True),
            manager,
        )

    rows = await ss.list_project_storytellers(db_session, project_id)
    assert [r.name for r in rows] == ["Ana", "Marcos", "Zelda"]


@pytest.mark.asyncio
async def test_update_own_storyteller_as_member(db_session: AsyncSession) -> None:
    ss = _import_service()
    project_id, _ = await _seed_project_with_manager(db_session)
    member = await _add_member(db_session, project_id, "member@test.com")

    st = await ss.create_storyteller(
        db_session,
        project_id,
        StorytellerCreate(name="Ana", sex="female", external_acceptance_confirmed=True),
        member,
    )

    updated = await ss.update_storyteller(
        db_session, st.id, StorytellerUpdate(dialect="Trumai"), member.id
    )
    assert updated.dialect == "Trumai"


@pytest.mark.asyncio
async def test_update_other_members_storyteller_blocked(
    db_session: AsyncSession,
) -> None:
    ss = _import_service()
    project_id, _ = await _seed_project_with_manager(db_session)
    author = await _add_member(db_session, project_id, "author@test.com")
    other = await _add_member(db_session, project_id, "other@test.com")

    st = await ss.create_storyteller(
        db_session,
        project_id,
        StorytellerCreate(name="Ana", sex="female", external_acceptance_confirmed=True),
        author,
    )

    with pytest.raises(AuthorizationError):
        await ss.update_storyteller(
            db_session, st.id, StorytellerUpdate(dialect="Trumai"), other.id
        )


@pytest.mark.asyncio
async def test_manager_can_update_any_storyteller(db_session: AsyncSession) -> None:
    ss = _import_service()
    project_id, manager = await _seed_project_with_manager(db_session)
    member = await _add_member(db_session, project_id, "member@test.com")

    st = await ss.create_storyteller(
        db_session,
        project_id,
        StorytellerCreate(name="Ana", sex="female", external_acceptance_confirmed=True),
        member,
    )

    updated = await ss.update_storyteller(
        db_session, st.id, StorytellerUpdate(dialect="Kuikuro"), manager.id
    )
    assert updated.dialect == "Kuikuro"


@pytest.mark.asyncio
async def test_update_storyteller_non_member_blocked(db_session: AsyncSession) -> None:
    ss = _import_service()
    project_id, manager = await _seed_project_with_manager(db_session)
    outsider = await make_user(db_session, email="outsider@test.com")

    st = await ss.create_storyteller(
        db_session,
        project_id,
        StorytellerCreate(name="Ana", sex="female", external_acceptance_confirmed=True),
        manager,
    )

    with pytest.raises(AuthorizationError):
        await ss.update_storyteller(
            db_session, st.id, StorytellerUpdate(dialect="Trumai"), outsider.id
        )


@pytest.mark.asyncio
async def test_platform_admin_can_edit_any_storyteller(
    db_session: AsyncSession,
) -> None:
    ss = _import_service()
    project_id, manager = await _seed_project_with_manager(db_session)
    admin = await make_user(db_session, email="admin@test.com", is_platform_admin=True)

    st = await ss.create_storyteller(
        db_session,
        project_id,
        StorytellerCreate(name="Ana", sex="female", external_acceptance_confirmed=True),
        manager,
    )

    updated = await ss.update_storyteller(
        db_session, st.id, StorytellerUpdate(name="Anna"), admin.id
    )
    assert updated.name == "Anna"


@pytest.mark.asyncio
async def test_update_storyteller_preserves_audit_fields(
    db_session: AsyncSession,
) -> None:
    ss = _import_service()
    project_id, manager = await _seed_project_with_manager(db_session)

    st = await ss.create_storyteller(
        db_session,
        project_id,
        StorytellerCreate(name="Ana", sex="female", external_acceptance_confirmed=True),
        manager,
    )
    confirmed_at = st.external_acceptance_confirmed_at
    confirmed_by = st.external_acceptance_confirmed_by

    await ss.update_storyteller(db_session, st.id, StorytellerUpdate(name="Anna"), manager.id)
    refreshed = await ss.get_storyteller(db_session, st.id)
    assert refreshed.name == "Anna"
    assert refreshed.external_acceptance_confirmed_at == confirmed_at
    assert refreshed.external_acceptance_confirmed_by == confirmed_by


@pytest.mark.asyncio
async def test_delete_own_storyteller_as_member(db_session: AsyncSession) -> None:
    ss = _import_service()
    project_id, _ = await _seed_project_with_manager(db_session)
    member = await _add_member(db_session, project_id, "member@test.com")

    st = await ss.create_storyteller(
        db_session,
        project_id,
        StorytellerCreate(name="Ana", sex="female", external_acceptance_confirmed=True),
        member,
    )

    await ss.delete_storyteller(db_session, st.id, member.id)

    with pytest.raises(NotFoundError):
        await ss.get_storyteller(db_session, st.id)


@pytest.mark.asyncio
async def test_delete_other_members_storyteller_blocked(
    db_session: AsyncSession,
) -> None:
    ss = _import_service()
    project_id, _ = await _seed_project_with_manager(db_session)
    author = await _add_member(db_session, project_id, "author@test.com")
    other = await _add_member(db_session, project_id, "other@test.com")

    st = await ss.create_storyteller(
        db_session,
        project_id,
        StorytellerCreate(name="Ana", sex="female", external_acceptance_confirmed=True),
        author,
    )

    with pytest.raises(AuthorizationError):
        await ss.delete_storyteller(db_session, st.id, other.id)


@pytest.mark.asyncio
async def test_manager_can_delete_any_storyteller(db_session: AsyncSession) -> None:
    ss = _import_service()
    project_id, manager = await _seed_project_with_manager(db_session)
    member = await _add_member(db_session, project_id, "member@test.com")

    st = await ss.create_storyteller(
        db_session,
        project_id,
        StorytellerCreate(name="Ana", sex="female", external_acceptance_confirmed=True),
        member,
    )

    await ss.delete_storyteller(db_session, st.id, manager.id)

    with pytest.raises(NotFoundError):
        await ss.get_storyteller(db_session, st.id)


@pytest.mark.asyncio
async def test_delete_storyteller_nulls_recording_link(
    db_session: AsyncSession,
) -> None:
    ss = _import_service()
    project_id, manager = await _seed_project_with_manager(db_session)

    st = await ss.create_storyteller(
        db_session,
        project_id,
        StorytellerCreate(name="Ana", sex="female", external_acceptance_confirmed=True),
        manager,
    )

    genre, sub = await make_oc_taxonomy(db_session)

    rec = await make_oc_recording(
        db_session,
        project_id,
        genre.id,
        sub.id,
        storyteller_id=st.id,
        user_id=manager.id,
        title="test",
        upload_status=UploadStatus.LOCAL,
    )
    assert rec.storyteller_id == st.id

    await ss.delete_storyteller(db_session, st.id, manager.id)

    await db_session.refresh(rec)
    assert rec.storyteller_id is None

    stmt2 = select(OC_Storyteller).where(OC_Storyteller.id == st.id)
    result2 = await db_session.execute(stmt2)
    assert result2.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_get_storyteller_not_found(db_session: AsyncSession) -> None:
    ss = _import_service()
    with pytest.raises(NotFoundError):
        await ss.get_storyteller(db_session, "does-not-exist")
