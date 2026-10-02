"""The server says which build, store and models are live, at a public `/api/version`.

A caller with no credential asks and gets the build id (the image's git SHA), the store, and the
two model ladders; the answer is never cached and never carries a secret. The deploy contract
that bakes the build id into the image is pinned here too.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
import yaml
from fastapi import FastAPI

from app.api.build import router as build_router
from app.core.config import Settings, get_settings

ROOT = Path(__file__).resolve().parent.parent
SENTINEL = "sentinel-must-never-be-served"
ANSWERED = {"build_id", "gcs_platform_bucket", "tripod_voice_model", "tripod_classifier_model"}


@pytest.fixture
async def ask() -> AsyncIterator:
    app = FastAPI()
    app.include_router(build_router, prefix="/api")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:

        async def _ask() -> httpx.Response:
            return await client.get("/api/version")

        yield _ask


async def test_anyone_can_ask_which_build_store_and_models_are_live(
    ask, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "build_id", "abc123")
    monkeypatch.setattr(settings, "gcs_platform_bucket", "the-platform-bucket")
    monkeypatch.setattr(settings, "tripod_voice_model", "voice-a, voice-b,voice-c")
    monkeypatch.setattr(settings, "tripod_classifier_model", "class-a,class-b")

    response = await ask()

    assert response.status_code == 200
    assert response.json() == {
        "build": "abc123",
        "store": "gcs:the-platform-bucket",
        "model": ["voice-a", "voice-b", "voice-c"],
        "classifier_model": ["class-a", "class-b"],
    }


async def test_the_answer_is_never_cached(ask) -> None:
    response = await ask()

    assert response.headers["cache-control"] == "no-store"


async def test_a_server_built_without_a_build_id_says_its_build_is_unknown(
    ask, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("GIT_SHA", raising=False)
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./unused.db")
    monkeypatch.setattr(get_settings(), "build_id", Settings(_env_file=None).build_id)

    response = await ask()

    assert response.json()["build"] == "unknown"


async def test_a_server_built_with_an_empty_build_id_says_its_build_is_unknown(
    ask, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GIT_SHA", "")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./unused.db")
    monkeypatch.setattr(get_settings(), "build_id", Settings(_env_file=None).build_id)

    response = await ask()

    assert response.json()["build"] == "unknown"


async def test_the_answer_names_the_build_the_image_was_built_from(
    ask, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GIT_SHA", "9f8e7d6c5b4a")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./unused.db")
    monkeypatch.setattr(get_settings(), "build_id", Settings(_env_file=None).build_id)

    response = await ask()

    assert response.json()["build"] == "9f8e7d6c5b4a"


async def test_no_secret_is_ever_part_of_the_answer(ask, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    sentinels = []
    for name, field in Settings.model_fields.items():
        if field.annotation in (str, str | None) and name not in ANSWERED:
            value = f"{SENTINEL}-{name}"
            monkeypatch.setattr(settings, name, value)
            sentinels.append(value)

    response = await ask()

    assert response.status_code == 200
    assert [value for value in sentinels if value in response.text] == []


def _docker_build_line(workflow: str) -> str:
    path = ROOT / ".github" / "workflows" / workflow
    steps = yaml.safe_load(path.read_text(encoding="utf-8"))["jobs"]["deploy"]["steps"]
    step = next(step for step in steps if step["name"] == "Build and Push Backend")
    return next(line for line in step["run"].splitlines() if line.startswith("docker build"))


@pytest.mark.parametrize("workflow", ["deploy.yml", "deploy-staging.yml"])
def test_every_deploy_bakes_the_commit_into_the_image_it_builds(workflow: str) -> None:
    build_line = _docker_build_line(workflow)

    assert "--build-arg GIT_SHA=${{ github.sha }}" in build_line


def test_the_image_declares_the_build_id_it_is_baked_with() -> None:
    final_stage = (ROOT / "Dockerfile").read_text(encoding="utf-8").split("FROM ")[-1]

    assert "ARG GIT_SHA" in final_stage
    assert "ENV GIT_SHA=${GIT_SHA}" in final_stage
