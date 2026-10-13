from __future__ import annotations

import asyncio
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.api.internalization_room import sessions as sessions_api
from app.services.internalization_room import earlier_passages as statuses
from app.services.internalization_room.hearing import HeardSpeech
from tests.tablet_turn_harness import the_turn_is_scripted
from tests.text_seam_harness import ScriptedAgent


def a_room_whose_guide_is_scripted(monkeypatch: pytest.MonkeyPatch) -> ScriptedAgent:
    guide = ScriptedAgent([])

    async def heard(*_: Any, **__: Any) -> HeardSpeech:
        return HeardSpeech(text="Noemi voltou para Belem com Rute")

    async def no_opening_ahead(*_: Any, **__: Any) -> None:
        return None

    the_turn_is_scripted(monkeypatch, heard=heard, model=guide)
    monkeypatch.setattr(sessions_api, "prepare_opening", no_opening_ahead)
    return guide


def a_session_per_request(test_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


def the_statuses_never_answer(monkeypatch: pytest.MonkeyPatch) -> asyncio.Event:
    started = asyncio.Event()

    async def never(*_: Any, **__: Any) -> dict[str, str]:
        started.set()
        await asyncio.Event().wait()
        return {}

    monkeypatch.setattr(statuses, "read_statuses", never)
    return started
