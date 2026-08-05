import importlib

import httpx
import pytest
from pydantic import ValidationError as PydanticValidationError

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.db.models.project import Project
from app.models.public_request import PublicProjectRequestCreate
from app.services import language_service, public_request_service
from tests.baker import make_language, make_user

verify_recaptcha_module = importlib.import_module("app.services.public_request.verify_recaptcha")


async def test_create_language_request(db_session):
    request = await public_request_service.create_language_request(
        db_session,
        requester_name="Ana Silva",
        requester_email="ana@example.com",
        name="Arara",
        code="ARA",
    )
    assert request.kind == "create_language"
    assert request.status == "pending"
    assert request.code == "ara"
    assert request.requester_email == "ana@example.com"


async def test_create_language_request_conflicts_with_existing_language(db_session):
    await make_language(db_session, name="Arara", code="ara")
    with pytest.raises(ConflictError):
        await public_request_service.create_language_request(
            db_session,
            requester_name="Ana Silva",
            requester_email="ana@example.com",
            name="Arara",
            code="ara",
        )


async def test_create_language_request_conflicts_with_existing_name_case_insensitive(db_session):
    await make_language(db_session, name="English", code="eng")
    with pytest.raises(ConflictError):
        await public_request_service.create_language_request(
            db_session,
            requester_name="Ana Silva",
            requester_email="ana@example.com",
            name="ENGLISH",
            code="enn",
        )


async def test_create_language_request_conflicts_with_pending_request(db_session):
    await public_request_service.create_language_request(
        db_session,
        requester_name="Ana Silva",
        requester_email="ana@example.com",
        name="Arara",
        code="ara",
    )
    with pytest.raises(ConflictError):
        await public_request_service.create_language_request(
            db_session,
            requester_name="Beto Souza",
            requester_email="beto@example.com",
            name="Arara do Norte",
            code="ara",
        )


async def test_create_language_request_conflicts_with_pending_name_case_insensitive(db_session):
    await public_request_service.create_language_request(
        db_session,
        requester_name="Ana Silva",
        requester_email="ana@example.com",
        name="Arara",
        code="ara",
    )
    with pytest.raises(ConflictError):
        await public_request_service.create_language_request(
            db_session,
            requester_name="Beto Souza",
            requester_email="beto@example.com",
            name="ARARA",
            code="arr",
        )


async def test_create_project_request(db_session):
    language = await make_language(db_session, code="prj")
    request = await public_request_service.create_project_request(
        db_session,
        requester_name="Ana Silva",
        requester_email="ana@example.com",
        name="Genesis Oral Stories",
        language_id=language.id,
        description="Documentation project",
    )
    assert request.kind == "create_project"
    assert request.status == "pending"
    assert request.language_id == language.id
    assert request.description == "Documentation project"


async def test_create_project_request_unknown_language(db_session):
    with pytest.raises(NotFoundError):
        await public_request_service.create_project_request(
            db_session,
            requester_name="Ana Silva",
            requester_email="ana@example.com",
            name="Genesis Oral Stories",
            language_id="missing-language-id",
        )


async def test_create_project_request_with_new_language(db_session):
    request = await public_request_service.create_project_request(
        db_session,
        requester_name="Ana Silva",
        requester_email="ana@example.com",
        name="Genesis Oral Stories",
        new_language_name="Arara",
        new_language_code="ARA",
    )
    assert request.kind == "create_project"
    assert request.language_id is None
    assert request.new_language_name == "Arara"
    assert request.new_language_code == "ara"


async def test_create_project_request_new_language_conflicts_case_insensitive(db_session):
    await make_language(db_session, name="English", code="eng")
    with pytest.raises(ConflictError):
        await public_request_service.create_project_request(
            db_session,
            requester_name="Ana Silva",
            requester_email="ana@example.com",
            name="Genesis Oral Stories",
            new_language_name="english",
            new_language_code="ptx",
        )
    with pytest.raises(ConflictError):
        await public_request_service.create_project_request(
            db_session,
            requester_name="Ana Silva",
            requester_email="ana@example.com",
            name="Genesis Oral Stories",
            new_language_name="Other Name",
            new_language_code="ENG",
        )


async def test_create_project_request_without_language_info(db_session):
    with pytest.raises(ValidationError):
        await public_request_service.create_project_request(
            db_session,
            requester_name="Ana Silva",
            requester_email="ana@example.com",
            name="Genesis Oral Stories",
        )


async def test_language_request_conflicts_with_pending_project_new_language(db_session):
    await public_request_service.create_project_request(
        db_session,
        requester_name="Ana Silva",
        requester_email="ana@example.com",
        name="Genesis Oral Stories",
        new_language_name="Arara",
        new_language_code="ara",
    )
    with pytest.raises(ConflictError):
        await public_request_service.create_language_request(
            db_session,
            requester_name="Beto Souza",
            requester_email="beto@example.com",
            name="arara",
            code="arz",
        )


async def test_verify_recaptcha_skipped_without_secret(monkeypatch):
    class _Settings:
        recaptcha_secret_key = ""

    monkeypatch.setattr(verify_recaptcha_module, "get_settings", lambda: _Settings())
    await public_request_service.verify_recaptcha("any-token")


async def test_verify_recaptcha_requires_token_when_secret_configured(monkeypatch):
    class _Settings:
        recaptcha_secret_key = "secret"

    monkeypatch.setattr(verify_recaptcha_module, "get_settings", lambda: _Settings())
    with pytest.raises(ValidationError):
        await public_request_service.verify_recaptcha(None)


async def test_verify_recaptcha_rejects_failed_verification(monkeypatch):
    class _Settings:
        recaptcha_secret_key = "secret"

    async def _failed_siteverify(secret: str, token: str) -> bool:
        return False

    monkeypatch.setattr(verify_recaptcha_module, "get_settings", lambda: _Settings())
    monkeypatch.setattr(verify_recaptcha_module, "_siteverify", _failed_siteverify)
    with pytest.raises(ValidationError):
        await public_request_service.verify_recaptcha("bad-token")


async def test_verify_recaptcha_accepts_valid_token(monkeypatch):
    class _Settings:
        recaptcha_secret_key = "secret"

    async def _ok_siteverify(secret: str, token: str) -> bool:
        return True

    monkeypatch.setattr(verify_recaptcha_module, "get_settings", lambda: _Settings())
    monkeypatch.setattr(verify_recaptcha_module, "_siteverify", _ok_siteverify)
    await public_request_service.verify_recaptcha("good-token")


async def test_verify_recaptcha_unavailable_on_http_error(monkeypatch):
    class _Settings:
        recaptcha_secret_key = "secret"

    async def _raise_http(secret: str, token: str) -> bool:
        raise httpx.HTTPError("boom")

    monkeypatch.setattr(verify_recaptcha_module, "get_settings", lambda: _Settings())
    monkeypatch.setattr(verify_recaptcha_module, "_siteverify", _raise_http)
    with pytest.raises(ValidationError, match="unavailable"):
        await public_request_service.verify_recaptcha("good-token")


async def test_verify_recaptcha_unavailable_on_malformed_response(monkeypatch):
    class _Settings:
        recaptcha_secret_key = "secret"

    async def _raise_value(secret: str, token: str) -> bool:
        raise ValueError("not json")

    monkeypatch.setattr(verify_recaptcha_module, "get_settings", lambda: _Settings())
    monkeypatch.setattr(verify_recaptcha_module, "_siteverify", _raise_value)
    with pytest.raises(ValidationError, match="unavailable"):
        await public_request_service.verify_recaptcha("good-token")


def test_public_project_request_rejects_both_language_modes():
    with pytest.raises(PydanticValidationError):
        PublicProjectRequestCreate(
            requester_name="Ana",
            requester_email="ana@example.com",
            name="Projeto",
            language_id="lang-1",
            new_language_name="Arara",
        )


async def test_create_language_request_stores_description(db_session):
    request = await public_request_service.create_language_request(
        db_session,
        requester_name="Ana Silva",
        requester_email="ana@example.com",
        name="Arara",
        code="ARA",
        description="Spoken along the Purus river.",
    )
    assert request.description == "Spoken along the Purus river."


async def test_create_language_request_description_is_optional(db_session):
    request = await public_request_service.create_language_request(
        db_session,
        requester_name="Ana Silva",
        requester_email="ana@example.com",
        name="Arara",
        code="ARA",
    )
    assert request.description is None


async def test_list_public_requests_filters_by_kind_and_status(db_session):
    language_request = await public_request_service.create_language_request(
        db_session,
        requester_name="Ana Silva",
        requester_email="ana@example.com",
        name="Arara",
        code="ara",
    )
    language = await make_language(db_session, name="Kokama", code="kos")
    await public_request_service.create_project_request(
        db_session,
        requester_name="Ana Silva",
        requester_email="ana@example.com",
        name="Projeto",
        language_id=language.id,
    )

    pending = await public_request_service.list_public_requests(db_session, status="pending")
    assert len(pending) == 2

    languages_only = await public_request_service.list_public_requests(
        db_session, kind="create_language"
    )
    assert [request.id for request in languages_only] == [language_request.id]


async def test_review_public_request_approve_creates_language(db_session):
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    request = await public_request_service.create_language_request(
        db_session,
        requester_name="Ana Silva",
        requester_email="ana@example.com",
        name="Arara",
        code="ara",
    )

    reviewed = await public_request_service.review_public_request(
        db_session, admin, request.id, "approved", None
    )

    assert reviewed.status == "approved"
    assert reviewed.reviewed_by == admin.id
    assert reviewed.created_entity_id is not None
    created = await language_service.get_language_by_code(db_session, "ara")
    assert created is not None
    assert created.id == reviewed.created_entity_id


async def test_review_public_request_approve_creates_project_with_new_language(db_session):
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    request = await public_request_service.create_project_request(
        db_session,
        requester_name="Ana Silva",
        requester_email="ana@example.com",
        name="Projeto Arara",
        new_language_name="Arara",
        new_language_code="ara",
    )

    reviewed = await public_request_service.review_public_request(
        db_session, admin, request.id, "approved", None
    )

    assert reviewed.status == "approved"
    created_language = await language_service.get_language_by_code(db_session, "ara")
    assert created_language is not None
    project = await db_session.get(Project, reviewed.created_entity_id)
    assert project is not None
    assert project.language_id == created_language.id


async def test_review_public_request_reject_creates_nothing(db_session):
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    request = await public_request_service.create_language_request(
        db_session,
        requester_name="Ana Silva",
        requester_email="ana@example.com",
        name="Arara",
        code="ara",
    )

    reviewed = await public_request_service.review_public_request(
        db_session, admin, request.id, "rejected", "Out of scope"
    )

    assert reviewed.status == "rejected"
    assert reviewed.created_entity_id is None
    assert reviewed.review_reason == "Out of scope"
    assert await language_service.get_language_by_code(db_session, "ara") is None


async def test_review_public_request_twice_conflicts(db_session):
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    request = await public_request_service.create_language_request(
        db_session,
        requester_name="Ana Silva",
        requester_email="ana@example.com",
        name="Arara",
        code="ara",
    )
    await public_request_service.review_public_request(
        db_session, admin, request.id, "approved", None
    )

    with pytest.raises(ConflictError, match="already been reviewed"):
        await public_request_service.review_public_request(
            db_session, admin, request.id, "rejected", None
        )


async def test_review_public_request_missing_raises_not_found(db_session):
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    with pytest.raises(NotFoundError, match="Public request not found"):
        await public_request_service.review_public_request(
            db_session, admin, "00000000-0000-0000-0000-000000000000", "approved", None
        )
