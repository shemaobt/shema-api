from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import FastAPI
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
