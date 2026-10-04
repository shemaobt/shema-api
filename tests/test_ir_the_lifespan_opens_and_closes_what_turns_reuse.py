from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from langdetect import detector_factory

from app import main
from app.core.config import Settings
from app.services.internalization_room import llm


def _settings() -> Settings:
    return Settings(database_url="sqlite+aiosqlite:///./test.db", anthropic_api_key="sk-ant-fake")


class _Answers:
    async def create(self, **kwargs: Any) -> SimpleNamespace:
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text="ok")],
            stop_reason="end_turn",
            model=kwargs["model"],
            usage=SimpleNamespace(
                input_tokens=1,
                output_tokens=1,
                cache_read_input_tokens=0,
                cache_creation_input_tokens=0,
                cache_creation=None,
            ),
        )


async def _nothing(*_: Any, **__: Any) -> int:
    return 0


@pytest.fixture
def quiet_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "setup_logging", lambda: None)
    for name in (
        "seed_books",
        "seed_agent_prompts",
        "seed_default_prompts",
        "init_qdrant",
        "close_qdrant",
        "close_db",
    ):
        monkeypatch.setattr(main, name, _nothing)
    monkeypatch.setattr(main, "_load_bhsa_background", lambda: None)


@pytest.fixture
def closed(monkeypatch: pytest.MonkeyPatch) -> list[object]:
    shut: list[object] = []

    class _ClosableClient:
        def __init__(self, **_: Any) -> None:
            self.messages = _Answers()

        async def close(self) -> None:
            shut.append(self)

    monkeypatch.setattr(llm.anthropic, "AsyncAnthropic", _ClosableClient)
    return shut


async def test_the_model_client_a_turn_reused_is_closed_when_the_server_stops(
    quiet_startup: None, closed: list[object]
) -> None:
    async with main.lifespan(FastAPI()):
        await llm.call_agent(system_prompt="s", user_content="u", settings=_settings())
        await llm.call_agent(system_prompt="s", user_content="u", settings=_settings())

    assert len(closed) == 1, (
        "o cliente de modelo ficava aberto depois que o servidor parava, com as conexões "
        "que ele guardava vivas até o processo morrer"
    )


async def test_the_language_profiles_are_loaded_before_the_first_turn_needs_them(
    quiet_startup: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(detector_factory, "_factory", None)

    async with main.lifespan(FastAPI()):
        loaded = detector_factory._factory

    assert loaded is not None, (
        "o langdetect carregava os perfis de língua na primeira fala do Guia, e o primeiro "
        "turno depois de cada deploy pagava isso na espera da equipe"
    )
