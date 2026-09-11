"""The text seam: her golden runner reaches our turn loop with a sentence, not a microphone.

Every path into a turn started at audio, so the question that matters most — does our voice
behave like the one that passed five golden sessions — had no cheap answer. The seam takes
the team's words as text, runs the real Guide, the real Validator and the real ladder, and
hands back what the judge reads: the Guide's spoken words and the outcome tag. Only STT and
TTS sit outside it. It exists only where a runner key is configured, and it never reaches a
tablet.
"""

from __future__ import annotations

import json
import sys
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import router
from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import register_exception_handlers

SEAM = "/api/internalization-room/text-seam"
RUNNER_KEY = "runner-de-teste"
GUIDE_LINE = "Olá, eu sou o Facilitador Digital. Vamos começar pelo todo."
TEAM_LINE = "Bom dia. Somos a equipe Terena. Pode continuar."


class _Agent:
    """The Guide and the Validator answering as this test's script says, one entry per call."""

    def __init__(self, script: list[Any]) -> None:
        self._script = list(script)
        self.guide_inputs: list[str] = []

    async def __call__(self, *, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        validating = "corrected_response" in system_prompt
        if not validating:
            self.guide_inputs.append(user_content)
        planned = self._script.pop(0) if self._script else None
        if planned is not None:
            return planned
        if validating:
            return json.dumps({"verdict": "pass", "issues": []})
        return GUIDE_LINE


def _the_models_answer(monkeypatch: pytest.MonkeyPatch, *script: Any) -> _Agent:
    module = sys.modules["app.services.internalization_room.run_turn"]
    agent = _Agent(list(script))
    monkeypatch.setattr(module, "call_agent", agent)
    return agent


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    from fastapi import FastAPI

    monkeypatch.setattr(
        get_settings(), "internalization_room_runner_key", RUNNER_KEY, raising=False
    )
    _the_models_answer(monkeypatch)

    test_app = FastAPI()
    test_app.include_router(router, prefix="/api/internalization-room")
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", headers={"X-Access-Code": RUNNER_KEY}
    ) as c:
        yield c


async def _a_session(client: httpx.AsyncClient, language: str = "Brazilian Portuguese") -> str:
    created = await client.post(f"{SEAM}/session", json={"pericopeId": "P01", "language": language})
    assert created.status_code == 200, created.text
    return created.json()["sessionId"]


async def test_a_runner_with_the_key_opens_a_session_on_the_passage(client) -> None:
    created = await client.post(
        f"{SEAM}/session", json={"pericopeId": "P01", "language": "Brazilian Portuguese"}
    )

    assert created.status_code == 200, created.text
    body = created.json()
    assert body["pericopeId"] == "P01"
    assert body["sessionId"], "a sessão abriu sem um id que o runner pudesse guardar"
    assert body["language"] == "pt", (
        "o roteiro dela nomeia a língua por extenso e a sala só falava em códigos, então "
        "'Brazilian Portuguese' era recusado como uma língua que a sala não fala"
    )


async def test_a_language_the_room_does_not_speak_is_refused_not_answered_in_another(
    client,
) -> None:
    created = await client.post(f"{SEAM}/session", json={"pericopeId": "P01", "language": "Terena"})

    assert created.status_code == 400, created.text


async def test_without_a_runner_key_the_seam_does_not_exist(client, monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "internalization_room_runner_key", "")

    created = await client.post(
        f"{SEAM}/session", json={"pericopeId": "P01", "language": "Brazilian Portuguese"}
    )

    assert created.status_code == 404, (
        "em produção a chave do runner não existe; a costura tem de responder como uma rota "
        "que não existe, nunca pedir uma credencial que ninguém recebeu"
    )


async def test_a_runner_with_the_wrong_key_is_refused(client) -> None:
    created = await client.post(
        f"{SEAM}/session",
        json={"pericopeId": "P01", "language": "Brazilian Portuguese"},
        headers={"X-Access-Code": "outra-chave"},
    )

    assert created.status_code == 401, created.text
