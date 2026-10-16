"""The golden doors a scene rehearsal case plays through: a session opened, a rehearsal kept
from the script's pieces and sent, and the Guide's system read after the cache break.

Fixtures are not exported: each module keeps the three-line fixture that calls
`a_golden_client`.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.services import internalization_room as room_service
from app.services.internalization_room import hearing, takes
from app.services.internalization_room.llm import CACHE_BREAK
from tests.hearing_harness import nothing_settles
from tests.text_seam_harness import BEARER, GOLDEN, RUNNER_KEY, the_app, the_models_answer

SANDAL = ["Ele tirou a sandália e deu pro Boaz."]


@asynccontextmanager
async def a_golden_client(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[httpx.AsyncClient]:
    monkeypatch.setattr(
        get_settings(), "internalization_room_runner_key", RUNNER_KEY, raising=False
    )
    the_models_answer(monkeypatch)
    nothing_settles(monkeypatch)

    async def _never_heard(*_: Any, **__: Any) -> Any:
        raise AssertionError("a porta dourada pediu ao reconhecedor que ouvisse uma frase")

    def _never_stored(*_: Any, **__: Any) -> Any:
        raise AssertionError("a porta dourada tocou o balde")

    monkeypatch.setattr(hearing, "transcribe_audio", _never_heard)
    monkeypatch.setattr(hearing, "transcribe_audio_detailed", _never_heard)
    monkeypatch.setattr(takes, "_store", _never_stored)
    transport = ASGITransport(app=the_app(db_session))
    async with httpx.AsyncClient(transport=transport, base_url="http://test", headers=BEARER) as c:
        yield c


async def an_open_session(client: httpx.AsyncClient, pericope: str = "P11") -> str:
    created = await client.post(
        f"{GOLDEN}/session", json={"pericopeId": pericope, "language": "Brazilian Portuguese"}
    )
    assert created.status_code == 200, created.text
    session_id = str(created.json()["sessionId"])
    opened = await client.post(
        f"{GOLDEN}/turn", json={"sessionId": session_id, "roomNote": "session_start"}
    )
    assert opened.status_code == 200, opened.text
    return session_id


async def a_sent_rehearsal(
    client: httpx.AsyncClient,
    session_id: str,
    scene: str | None,
    turn_id: str = "turno-1",
    pieces: list[str] = SANDAL,
) -> httpx.Response:
    kept = await client.post(
        f"{GOLDEN}/rehearsal", json={"sessionId": session_id, "sceneId": scene, "pieces": pieces}
    )
    assert kept.status_code == 200, kept.text
    return await client.post(
        f"{GOLDEN}/rehearsal/send",
        json={
            "sessionId": session_id,
            "rehearsalId": kept.json()["rehearsalId"],
            "turnId": turn_id,
        },
    )


def after_the_break(system_prompt: str) -> str:
    return system_prompt.partition(CACHE_BREAK)[2]


async def the_room_stands_in(db: AsyncSession, session_id: str, moment: dict[str, Any]) -> None:
    stored = await room_service.get_session(db, session_id)
    *earlier, guide = [dict(message) for message in stored.messages or []]
    guide["moment"] = {"before": {"at": "familiarization"}, "after": moment, "by": []}
    stored.messages = [*earlier, guide]
    await db.commit()


class Both:
    def __init__(self) -> None:
        self.validator_inputs: list[str] = []
        self.guide_systems: list[str] = []

    async def __call__(self, *, system_prompt: str, user_content: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            self.validator_inputs.append(f"{system_prompt}\n{user_content}")
            return json.dumps({"verdict": "pass", "issues": []})
        self.guide_systems.append(system_prompt)
        return "Obrigado. Vamos ver essa cena juntos."
