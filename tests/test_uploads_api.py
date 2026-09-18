from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import FastAPI
from google.api_core.exceptions import Forbidden, ServiceUnavailable
from httpx import ASGITransport

from app.api.uploads import router as uploads_router
from app.core.database import get_db
from app.core.exceptions import register_exception_handlers
from app.services.auth.issue_tokens import issue_tokens
from tests.baker import make_user


@pytest.fixture()
async def client(db_session):
    test_app = FastAPI()
    test_app.include_router(uploads_router, prefix="/api/uploads")
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _auth_header(db_session) -> dict[str, str]:
    user = await make_user(db_session, email="uploader@example.com")
    access, _refresh = await issue_tokens(db_session, user)
    return {"Authorization": f"Bearer {access}"}


def _png() -> dict[str, tuple[str, bytes, str]]:
    return {"file": ("icon.png", b"\x89PNG\r\n\x1a\n", "image/png")}


@pytest.mark.parametrize("folder", ["app-icons", "avatars", "project-images", "images"])
async def test_allowed_folders_reach_storage_unchanged(db_session, client, folder) -> None:
    headers = await _auth_header(db_session)
    with patch("app.api.uploads.upload_image", new=AsyncMock(return_value="https://x/y.png")) as up:
        response = await client.post(
            f"/api/uploads/image?folder={folder}", files=_png(), headers=headers
        )

    assert response.status_code == 200
    assert up.await_args.kwargs["folder"] == folder


async def test_unknown_folder_falls_back_to_images(db_session, client) -> None:
    headers = await _auth_header(db_session)
    with patch("app.api.uploads.upload_image", new=AsyncMock(return_value="https://x/y.png")) as up:
        response = await client.post(
            "/api/uploads/image?folder=../escape", files=_png(), headers=headers
        )

    assert response.status_code == 200
    assert up.await_args.kwargs["folder"] == "images"


async def test_upload_requires_authentication(client) -> None:
    response = await client.post("/api/uploads/image?folder=avatars", files=_png())

    assert response.status_code == 401


async def test_unsupported_file_type_is_rejected_as_bad_request(db_session, client) -> None:
    headers = await _auth_header(db_session)
    files = {"file": ("notes.txt", b"hello", "text/plain")}

    response = await client.post("/api/uploads/image?folder=avatars", files=files, headers=headers)

    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


def _client_failing_on_upload(error: Exception) -> MagicMock:
    gcs = MagicMock()
    gcs.bucket.return_value.blob.return_value.upload_from_string.side_effect = error
    return gcs


async def test_unreadable_credentials_report_service_unavailable(db_session, client) -> None:
    headers = await _auth_header(db_session)
    boom = IsADirectoryError(21, "Is a directory", "/etc/gcs/signing-key.json")

    with patch("app.services.storage.upload.storage.Client", side_effect=boom):
        response = await client.post(
            "/api/uploads/image?folder=avatars", files=_png(), headers=headers
        )

    assert response.status_code == 503
    body = response.json()
    assert body["code"] == "STORAGE_UNAVAILABLE"
    assert "Image storage is unavailable" in body["detail"]


async def test_credentials_refused_by_gcs_report_service_unavailable(db_session, client) -> None:
    headers = await _auth_header(db_session)
    gcs = _client_failing_on_upload(Forbidden("storage.objects.create denied"))

    with patch("app.services.storage.upload.storage.Client", return_value=gcs):
        response = await client.post(
            "/api/uploads/image?folder=avatars", files=_png(), headers=headers
        )

    assert response.status_code == 503
    body = response.json()
    assert body["code"] == "STORAGE_UNAVAILABLE"
    assert "credentials" in body["detail"]


async def test_gcs_server_error_reports_bad_gateway_not_misconfiguration(
    db_session, client
) -> None:
    headers = await _auth_header(db_session)
    gcs = _client_failing_on_upload(ServiceUnavailable("backend error"))

    with patch("app.services.storage.upload.storage.Client", return_value=gcs):
        response = await client.post(
            "/api/uploads/image?folder=avatars", files=_png(), headers=headers
        )

    assert response.status_code == 502
    body = response.json()
    assert body["code"] == "UPSTREAM_ERROR"
    assert "service account" not in body["detail"]


async def test_storage_failure_log_carries_the_original_gcs_error(
    db_session, client, caplog
) -> None:
    headers = await _auth_header(db_session)
    boom = IsADirectoryError(21, "Is a directory", "/etc/gcs/signing-key.json")

    with (
        caplog.at_level(logging.ERROR, logger="app.core.exceptions"),
        patch("app.services.storage.upload.storage.Client", side_effect=boom),
    ):
        await client.post("/api/uploads/image?folder=avatars", files=_png(), headers=headers)

    record = next(r for r in caplog.records if r.name == "app.core.exceptions")
    assert record.exc_info is not None
    assert "signing-key.json" in logging.Formatter().formatException(record.exc_info)
