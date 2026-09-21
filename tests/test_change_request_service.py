from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.exceptions import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.db.models.change_request import ChangeRequest
from app.db.models.language import Language
from app.db.models.project import ProjectUserAccess
from app.models.change_request import ChangeRequestCreate
from app.services import change_request_service
from tests.baker import make_language, make_project, make_project_user_access, make_user


async def _pending(db, **kwargs) -> ChangeRequest:
    request = ChangeRequest(status="pending", **kwargs)
    db.add(request)
    await db.commit()
    await db.refresh(request)
    return request


async def _project_access(db, project_id, user_id):
    result = await db.execute(
        select(ProjectUserAccess).where(
            ProjectUserAccess.project_id == project_id,
            ProjectUserAccess.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


@pytest.mark.asyncio
async def test_create_project_request(db_session) -> None:
    user = await make_user(db_session)
    lang = await make_language(db_session, code="prj")
    payload = ChangeRequestCreate(
        kind="create_project", name="Genesis", language_id=lang.id, description="d"
    )
    request = await change_request_service.create_change_request(db_session, user.id, payload)
    assert request.status == "pending"
    assert request.kind == "create_project"
    assert request.name == "Genesis"


@pytest.mark.asyncio
async def test_create_project_request_requires_name_and_language(db_session) -> None:
    user = await make_user(db_session)
    with pytest.raises(ValidationError):
        await change_request_service.create_change_request(
            db_session, user.id, ChangeRequestCreate(kind="create_project", name="X")
        )


@pytest.mark.asyncio
async def test_create_project_request_unknown_language(db_session) -> None:
    user = await make_user(db_session)
    with pytest.raises(NotFoundError):
        await change_request_service.create_change_request(
            db_session,
            user.id,
            ChangeRequestCreate(kind="create_project", name="X", language_id="missing"),
        )


@pytest.mark.asyncio
async def test_create_project_request_with_new_language(db_session) -> None:
    user = await make_user(db_session)
    payload = ChangeRequestCreate(
        kind="create_project",
        name="Genesis",
        new_language_name="Arara",
        new_language_code="ARA",
    )
    request = await change_request_service.create_change_request(db_session, user.id, payload)
    assert request.language_id is None
    assert request.new_language_name == "Arara"
    assert request.new_language_code == "ara"


@pytest.mark.asyncio
async def test_create_project_request_new_language_bad_code(db_session) -> None:
    user = await make_user(db_session)
    with pytest.raises(ValidationError):
        await change_request_service.create_change_request(
            db_session,
            user.id,
            ChangeRequestCreate(
                kind="create_project", name="X", new_language_name="Arara", new_language_code="ar"
            ),
        )


@pytest.mark.asyncio
async def test_create_project_request_rejects_both_language_sources(db_session) -> None:
    user = await make_user(db_session)
    lang = await make_language(db_session, code="prj")
    with pytest.raises(ValidationError):
        await change_request_service.create_change_request(
            db_session,
            user.id,
            ChangeRequestCreate(
                kind="create_project",
                name="X",
                language_id=lang.id,
                new_language_name="Arara",
                new_language_code="ara",
            ),
        )


@pytest.mark.asyncio
async def test_approve_create_project_with_new_language(db_session) -> None:
    admin = await make_user(db_session, email="a@example.com", is_platform_admin=True)
    requester = await make_user(db_session, email="r@example.com")
    request = await _pending(
        db_session,
        kind="create_project",
        requester_user_id=requester.id,
        name="Genesis",
        new_language_name="Arara",
        new_language_code="ara",
    )
    result, _ = await change_request_service.review_change_request(
        db_session, admin, request.id, "approved", None, True
    )
    assert result.status == "approved"
    from app.db.models.project import Project

    project = await db_session.get(Project, result.created_entity_id)
    assert project is not None
    language = await db_session.get(Language, project.language_id)
    assert language is not None
    assert language.name == "Arara"
    assert language.code == "ara"
    assert language.created_by == requester.id
    access = await _project_access(db_session, result.created_entity_id, requester.id)
    assert access is not None and access.role == "manager"


@pytest.mark.asyncio
async def test_approve_create_project_new_language_duplicate_conflicts(db_session) -> None:
    admin = await make_user(db_session, email="a@example.com", is_platform_admin=True)
    requester = await make_user(db_session, email="r@example.com")
    await make_language(db_session, code="dup")
    request = await _pending(
        db_session,
        kind="create_project",
        requester_user_id=requester.id,
        name="Genesis",
        new_language_name="Dupe",
        new_language_code="dup",
    )
    with pytest.raises(ConflictError):
        await change_request_service.review_change_request(
            db_session, admin, request.id, "approved", None, True
        )


@pytest.mark.asyncio
async def test_create_language_request_lowercases_code(db_session) -> None:
    user = await make_user(db_session)
    request = await change_request_service.create_change_request(
        db_session, user.id, ChangeRequestCreate(kind="create_language", name="Kokama", code="KOK")
    )
    assert request.code == "kok"


@pytest.mark.asyncio
async def test_create_language_request_bad_code(db_session) -> None:
    user = await make_user(db_session)
    with pytest.raises(ValidationError):
        await change_request_service.create_change_request(
            db_session, user.id, ChangeRequestCreate(kind="create_language", name="X", code="ab")
        )


@pytest.mark.asyncio
async def test_edit_language_request_scoped_to_managed_project(db_session) -> None:
    manager = await make_user(db_session, email="m@example.com")
    lang = await make_language(db_session, code="edt")
    project = await make_project(db_session, language_id=lang.id)
    await make_project_user_access(db_session, project.id, manager.id, role="manager")
    request = await change_request_service.create_change_request(
        db_session,
        manager.id,
        ChangeRequestCreate(kind="edit_language", language_id=lang.id, name="New Name"),
    )
    assert request.kind == "edit_language"


@pytest.mark.asyncio
async def test_edit_language_request_bad_code(db_session) -> None:
    manager = await make_user(db_session, email="m@example.com")
    lang = await make_language(db_session, code="edt")
    project = await make_project(db_session, language_id=lang.id)
    await make_project_user_access(db_session, project.id, manager.id, role="manager")
    with pytest.raises(ValidationError):
        await change_request_service.create_change_request(
            db_session,
            manager.id,
            ChangeRequestCreate(kind="edit_language", language_id=lang.id, code="ab"),
        )


@pytest.mark.asyncio
async def test_edit_language_request_forbidden_when_not_managed(db_session) -> None:
    user = await make_user(db_session)
    lang = await make_language(db_session, code="edt")
    with pytest.raises(AuthorizationError):
        await change_request_service.create_change_request(
            db_session,
            user.id,
            ChangeRequestCreate(kind="edit_language", language_id=lang.id, name="New"),
        )


@pytest.mark.asyncio
async def test_approve_create_project_grants_manager_access(db_session) -> None:
    admin = await make_user(db_session, email="a@example.com", is_platform_admin=True)
    requester = await make_user(db_session, email="r@example.com")
    lang = await make_language(db_session, code="prj")
    request = await _pending(
        db_session,
        kind="create_project",
        requester_user_id=requester.id,
        name="Genesis",
        language_id=lang.id,
    )
    result, _ = await change_request_service.review_change_request(
        db_session, admin, request.id, "approved", None, True
    )
    assert result.status == "approved"
    assert result.created_entity_id is not None
    access = await _project_access(db_session, result.created_entity_id, requester.id)
    assert access is not None
    assert access.role == "manager"


@pytest.mark.asyncio
async def test_approve_create_project_without_grant(db_session) -> None:
    admin = await make_user(db_session, email="a@example.com", is_platform_admin=True)
    requester = await make_user(db_session, email="r@example.com")
    lang = await make_language(db_session, code="prj")
    request = await _pending(
        db_session,
        kind="create_project",
        requester_user_id=requester.id,
        name="Genesis",
        language_id=lang.id,
    )
    result, _ = await change_request_service.review_change_request(
        db_session, admin, request.id, "approved", None, False
    )
    access = await _project_access(db_session, result.created_entity_id, requester.id)
    assert access is None


@pytest.mark.asyncio
async def test_approve_create_language_stamps_creator(db_session) -> None:
    admin = await make_user(db_session, email="a@example.com", is_platform_admin=True)
    requester = await make_user(db_session, email="r@example.com")
    request = await _pending(
        db_session,
        kind="create_language",
        requester_user_id=requester.id,
        name="Kokama",
        code="kok",
    )
    result, _ = await change_request_service.review_change_request(
        db_session, admin, request.id, "approved", None, False
    )
    language = await db_session.get(Language, result.created_entity_id)
    assert language.created_by == requester.id
    assert language.code == "kok"


@pytest.mark.asyncio
async def test_approve_edit_language_applies_changes(db_session) -> None:
    admin = await make_user(db_session, email="a@example.com", is_platform_admin=True)
    requester = await make_user(db_session, email="r@example.com")
    lang = await make_language(db_session, code="old", name="Old")
    request = await _pending(
        db_session,
        kind="edit_language",
        requester_user_id=requester.id,
        language_id=lang.id,
        name="New",
        code="new",
    )
    await change_request_service.review_change_request(
        db_session, admin, request.id, "approved", None, False
    )
    updated = await db_session.get(Language, lang.id)
    assert updated.name == "New"
    assert updated.code == "new"


@pytest.mark.asyncio
async def test_reject_does_not_apply(db_session) -> None:
    admin = await make_user(db_session, email="a@example.com", is_platform_admin=True)
    requester = await make_user(db_session, email="r@example.com")
    request = await _pending(
        db_session, kind="create_language", requester_user_id=requester.id, name="X", code="xxx"
    )
    result, _ = await change_request_service.review_change_request(
        db_session, admin, request.id, "rejected", "not now", False
    )
    assert result.status == "rejected"
    assert result.created_entity_id is None


@pytest.mark.asyncio
async def test_review_non_pending_conflicts(db_session) -> None:
    admin = await make_user(db_session, email="a@example.com", is_platform_admin=True)
    requester = await make_user(db_session, email="r@example.com")
    request = await _pending(
        db_session, kind="create_language", requester_user_id=requester.id, name="X", code="xxx"
    )
    await change_request_service.review_change_request(
        db_session, admin, request.id, "rejected", None, False
    )
    with pytest.raises(ConflictError):
        await change_request_service.review_change_request(
            db_session, admin, request.id, "approved", None, False
        )


@pytest.mark.asyncio
async def test_approve_create_language_duplicate_code_conflicts(db_session) -> None:
    admin = await make_user(db_session, email="a@example.com", is_platform_admin=True)
    requester = await make_user(db_session, email="r@example.com")
    await make_language(db_session, code="dup")
    request = await _pending(
        db_session, kind="create_language", requester_user_id=requester.id, name="X", code="dup"
    )
    with pytest.raises(ConflictError):
        await change_request_service.review_change_request(
            db_session, admin, request.id, "approved", None, False
        )


@pytest.mark.asyncio
async def test_list_and_mine(db_session) -> None:
    requester = await make_user(db_session, email="r@example.com")
    await _pending(
        db_session, kind="create_language", requester_user_id=requester.id, name="X", code="xxx"
    )
    rows = await change_request_service.list_change_requests(db_session, kind="create_language")
    assert len(rows) == 1
    _, user = rows[0]
    assert user.email == "r@example.com"
    mine = await change_request_service.list_my_change_requests(db_session, requester.id)
    assert len(mine) == 1


def test_apply_never_commits_so_the_approval_lands_as_one_transaction() -> None:
    """The write and the status stamp commit together, or neither does.

    An inner ``commit()`` in ``_apply`` persisted the language before the request was stamped;
    a failure in between left the request ``pending`` over an entity that already existed, and
    the retry raised ``ConflictError`` on the taken code — the request could never be approved.
    Reading the source is what keeps the rule, because the failure it guards only shows up when
    the outer commit dies.
    """
    source = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "services"
        / "change_request"
        / "review_change_request.py"
    ).read_text()
    after_apply = source.split("async def _apply(")[1]
    apply_body = after_apply.split("async def _create_requested_language(")[0]

    assert "db.commit()" not in apply_body
    assert "db.flush()" in apply_body
    assert source.count("await db.commit()") == 1
