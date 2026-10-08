"""What the two golden-run budget tests lend each other: a charged call and a wire to carry it."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx
import pytest


def charged_call(
    role: str,
    cost: float | None,
    *,
    input_tokens: int = 1000,
    output_tokens: int = 50,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> dict[str, Any]:
    return {
        "role": role,
        "rung": "claude-fable-5-1",
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_tokens": cache_read_tokens,
        "cache_write_tokens": cache_write_tokens,
        "latency_ms": 1000,
        "cost_usd": cost,
    }


def the_room_answers(
    monkeypatch: pytest.MonkeyPatch, answer: Callable[[httpx.Request], httpx.Response]
) -> None:
    made = httpx.AsyncClient

    def _client(**kwargs: Any) -> httpx.AsyncClient:
        return made(**{**kwargs, "transport": httpx.MockTransport(answer)})

    monkeypatch.setattr(httpx, "AsyncClient", _client)
