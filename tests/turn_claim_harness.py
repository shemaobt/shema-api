"""What a case about the turn claim needs: a Guide the case can park, a voice that keeps what it
said, the team's spoken turn, and the claim written on the row as another instance would.

Fixtures are not exported: each module keeps the three-line `voice` fixture calling `a_voice`.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import update

from app.api.internalization_room import sessions as sessions_api
from app.core.config import get_settings
from app.core.exceptions import UpstreamServiceError
from app.db.models.internalization_room import IRSession
from app.services.internalization_room import turn_dedup
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.sessions import get_session
from app.services.internalization_room.synthesize_facilitator_speech import facilitator_speech_key
from app.services.platform.tts import SynthesizedSpeech
from tests.release_harness import PREFIX
from tests.turn_harness import the_room_agent_is

OPENING = "Eu sou o Guia. Hoje a historia e a de Rute, que ficou com Noemi."
REPLY = "Vamos ficar nesta cena. O que voces contariam?"
SAID = "Noemi voltou para Belem com Rute"


class Guide:
    """The Guide: its first line parks until the case lets it answer, and every call counts.

    `lines` is what each call answers in turn, the last one repeating. `first_takes` makes the
    first line answer after that many seconds instead of waiting on `answer`, and `first_fails`
    makes it raise the provider's failure instead of answering at all. `given` keeps, written
    out, the conversation each call was handed.
    """

    def __init__(self, lines: tuple[str, ...] = (OPENING, REPLY)) -> None:
        self.lines = lines
        self.asked = 0
        self.given: list[str] = []
        self.thinking = asyncio.Event()
        self.answer = asyncio.Event()
        self.first_takes: float | None = None
        self.first_fails = False
        self.reply_takes = 0.0

    async def __call__(self, *, system_prompt: str, **kwargs: Any) -> str:
        if "corrected_response" in system_prompt:
            return '{"verdict": "pass", "issues": []}'
        self.asked += 1
        self.given.append(repr(kwargs.get("conversation")))
        line = self.lines[min(self.asked, len(self.lines)) - 1]
        if self.asked > 1:
            await asyncio.sleep(self.reply_takes)
            return line
        self.thinking.set()
        if self.first_takes is None:
            await self.answer.wait()
        else:
            await asyncio.sleep(self.first_takes)
        if self.first_fails:
            raise UpstreamServiceError("o provedor nao respondeu")
        return line


def the_guide_is(monkeypatch: pytest.MonkeyPatch, guide: Guide) -> Guide:
    the_room_agent_is(monkeypatch, turn=guide)
    return guide


def dead_after() -> timedelta:
    """Her lease's life: the turn bound and thirty seconds more."""
    return timedelta(milliseconds=get_settings().internalization_room_turn_bound_ms + 30_000)


def clip_of(text: str) -> str:
    return facilitator_speech_key(text, language="pt")


class Voice:
    """The synthesiser, naming each clip by its words and keeping every line it was given."""

    def __init__(self) -> None:
        self.said: list[str] = []

    async def __call__(self, text: str, **_: Any) -> tuple[SynthesizedSpeech, bool]:
        self.said.append(text)
        entry = SynthesizedSpeech(
            audio=b"audio", mime_type="audio/mpeg", etag="e", cached=False, key=clip_of(text)
        )
        return entry, False


def a_voice(monkeypatch: pytest.MonkeyPatch, *, hears: str = SAID) -> Voice:
    """The room's voice kept, every recording heard as `hears`, and nothing settled later."""
    voiced = Voice()

    async def heard(*_: Any, **__: Any) -> HeardSpeech:
        return HeardSpeech(text=hears)

    async def settled(**_: Any) -> None:
        return None

    monkeypatch.setattr(sessions_api.room, "synthesize_facilitator_speech", voiced)
    monkeypatch.setattr(sessions_api, "heard_speech", heard)
    monkeypatch.setattr(sessions_api, "settle_coverage", settled)
    return voiced


async def speak(client: httpx.AsyncClient, session_id: str, turn_id: str) -> httpx.Response:
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/turns",
        data={"turn_id": turn_id},
        files={"file": ("resposta.m4a", b"audio", "audio/m4a")},
    )


async def conversation(rival_factory, session_id: str) -> list[tuple[str, str]]:
    async with rival_factory() as fresh:
        reread = await get_session(fresh, session_id)
    return [(message["role"], message["text"]) for message in reread.messages or []]


async def claim_on_the_row(rival_factory, session_id: str, turn_id: str, at: datetime) -> None:
    async with rival_factory() as other_instance:
        await other_instance.execute(
            update(IRSession)
            .where(IRSession.id == session_id)
            .values(
                opening_claim_turn_id=turn_id,
                opening_claimed_at=at,
                updated_at=IRSession.updated_at,
            )
        )
        await other_instance.commit()


def another_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every request from here on lands on a process whose in-flight registry never saw the
    ones before it, as a second Cloud Run instance's does."""
    monkeypatch.setattr(turn_dedup, "_in_flight", {})
