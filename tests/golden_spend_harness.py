"""What the golden-run tests lend each other: a charged call, a wire, a shelf and its args."""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest

from scripts import bt_golden_runner
from tests.text_seam_harness import RUNNER_KEY

STAMP = "2026-10-08T12-00-00"
BT_BASE_URL = "http://room/api/internalization-room/text-seam/back-translation/"


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


GOLDEN_PRICED = [charged_call("guide", 2.0), charged_call("validator", 1.0)]
BT_PRICED = [charged_call("analyst", 2.0), charged_call("speaker", 1.0)]


def golden_shelf(tmp_path: Path, *scripts: tuple[str, str, int]) -> Path:
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    for name, pericope, turns in scripts:
        (sessions / f"{name}.json").write_text(
            json.dumps(
                {
                    "name": name,
                    "pericopeId": pericope,
                    "language": "Brazilian Portuguese",
                    "turns": [{"team": f"fala {n}"} for n in range(turns)],
                }
            ),
            encoding="utf-8",
        )
    return sessions


def golden_args(sessions: Path, out: Path, **over: Any) -> argparse.Namespace:
    given: dict[str, Any] = {
        "base_url": "http://room/api/internalization-room/",
        "script": None,
        "sessions": str(sessions),
        "only": None,
        "out": str(out),
        "turns": None,
        "access_code": RUNNER_KEY,
        "stamp": STAMP,
        "rejudge": None,
        "budget_usd": None,
    }
    return argparse.Namespace(**{**given, **over})


def bt_shelf(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *scripts: tuple[str, str, int],
    expect: dict[str, Any] | None = None,
) -> None:
    shelf = tmp_path / "bt"
    shelf.mkdir()
    for name, pericope, rounds in scripts:
        (shelf / f"{name}.json").write_text(
            json.dumps(
                {
                    "name": name,
                    "pericopeId": pericope,
                    "language": "Brazilian Portuguese",
                    "draft": {"clips": [{"key": "S1", "durationMs": 20000}]},
                    "rounds": [
                        {
                            "frases": [
                                {"clipKey": "S1", "coversFrom": 0, "coversTo": 10, "text": "Oi."}
                            ],
                            "expect": expect or {"conferida": True, "findings": []},
                        }
                        for _ in range(rounds)
                    ],
                }
            ),
            encoding="utf-8",
        )
    monkeypatch.setattr(bt_golden_runner, "BT_DIR", shelf)


def bt_args(out: Path, **over: Any) -> argparse.Namespace:
    given: dict[str, Any] = {
        "base_url": BT_BASE_URL,
        "script": None,
        "out": str(out),
        "access_code": RUNNER_KEY,
        "budget_usd": None,
    }
    return argparse.Namespace(**{**given, **over})
