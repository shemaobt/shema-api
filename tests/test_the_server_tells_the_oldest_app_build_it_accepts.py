"""The version answer names the oldest app build the room accepts on each platform.

A tablet compares its own build number with the answer; 0 means the room sets no minimum.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pydantic
import pytest
from fastapi import FastAPI

from app.api.build import router as build_router
from app.core.config import Settings, get_settings
from app.main import create_app
from tests.deploy_harness import deploy_env_vars

DATABASE_URL = "sqlite+aiosqlite:///./test.db"


@pytest.fixture
async def ask() -> AsyncIterator:
    app = FastAPI()
    app.include_router(build_router, prefix="/api")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:

        async def _ask() -> httpx.Response:
            return await client.get("/api/version")

        yield _ask


async def test_the_version_answer_names_the_oldest_build_the_room_accepts_on_each_platform(
    ask, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "internalization_room_minimum_app_ios", 12)
    monkeypatch.setattr(settings, "internalization_room_minimum_app_android", 14)

    response = await ask()

    assert response.status_code == 200
    assert response.json()["minimum_app"] == {"ios": 12, "android": 14}


async def test_a_server_with_no_minimum_set_accepts_every_build(
    ask, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("INTERNALIZATION_ROOM_MINIMUM_APP_IOS", raising=False)
    monkeypatch.delenv("INTERNALIZATION_ROOM_MINIMUM_APP_ANDROID", raising=False)
    untouched = Settings(database_url=DATABASE_URL, _env_file=None)
    settings = get_settings()
    for field in (
        "internalization_room_minimum_app_ios",
        "internalization_room_minimum_app_android",
    ):
        monkeypatch.setattr(settings, field, getattr(untouched, field))

    response = await ask()

    assert response.json()["minimum_app"] == {"ios": 0, "android": 0}


def test_each_minimum_is_read_from_the_deployments_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INTERNALIZATION_ROOM_MINIMUM_APP_IOS", "7")
    monkeypatch.setenv("INTERNALIZATION_ROOM_MINIMUM_APP_ANDROID", "9")

    settings = Settings(database_url=DATABASE_URL, _env_file=None)

    assert settings.internalization_room_minimum_app_ios == 7
    assert settings.internalization_room_minimum_app_android == 9


def test_a_negative_minimum_is_refused_at_boot(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTERNALIZATION_ROOM_MINIMUM_APP_IOS", "-1")

    with pytest.raises(pydantic.ValidationError):
        Settings(database_url=DATABASE_URL, _env_file=None)


async def test_anyone_can_read_the_minimum_without_a_credential() -> None:
    transport = httpx.ASGITransport(app=create_app())

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/version")

    assert response.status_code == 200
    assert set(response.json()["minimum_app"]) == {"ios", "android"}


@pytest.mark.parametrize(
    "key", ["INTERNALIZATION_ROOM_MINIMUM_APP_IOS", "INTERNALIZATION_ROOM_MINIMUM_APP_ANDROID"]
)
def test_the_production_deploy_names_both_minimums_as_whole_numbers(key: str) -> None:
    deployed = deploy_env_vars("deploy.yml")

    assert int(deployed[key]) >= 0
