"""A golden run that has spent its budget starts no further session, and says what it left.

The 7-8 October runs cost about US$ 75 and US$ 94 against US$ 90 of credits, and nothing
stopped a run before the credits did. The room is replaced here by a wire that charges a
known price per turn, so the money is the test's own arithmetic and not a model's.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from scripts import golden_runner
from tests.text_seam_harness import A_VERDICT, GUIDE_LINE, RUNNER_KEY, the_judge_answers

STAMP = "2026-10-08T12-00-00"


def _charged(role: str, cost: float | None) -> dict[str, Any]:
    return {
        "role": role,
        "rung": "claude-fable-5-1",
        "input_tokens": 1000,
        "output_tokens": 50,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "latency_ms": 1000,
        "cost_usd": cost,
    }


@pytest.fixture()
def opened(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    sessions: list[str] = []

    def _room(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/golden/session"):
            sessions.append(json.loads(request.content)["pericopeId"])
            return httpx.Response(200, json={"sessionId": f"s-{len(sessions)}"})
        return httpx.Response(
            200,
            json={
                "guideText": GUIDE_LINE,
                "outcome": "pass",
                "usage": [_charged("guide", 2.0), _charged("validator", 1.0)],
            },
        )

    made = httpx.AsyncClient

    def _client(**kwargs: Any) -> httpx.AsyncClient:
        return made(**{**kwargs, "transport": httpx.MockTransport(_room)})

    monkeypatch.setattr(httpx, "AsyncClient", _client)
    return sessions


def _shelf(tmp_path: Path, *scripts: tuple[str, str, int]) -> Path:
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


def _args(sessions: Path, out: Path, **over: Any) -> argparse.Namespace:
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


async def test_a_run_past_its_budget_starts_no_further_session_and_names_them(
    opened: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    the_judge_answers(monkeypatch)
    sessions = _shelf(tmp_path, ("P01-a", "P01", 2), ("P01-b", "P01", 1), ("P02-c", "P02", 1))

    exit_code = await golden_runner.run(_args(sessions, tmp_path / "reports", budget_usd=5.0))

    assert opened == ["P01"], (
        "dois turnos de US$ 3 passam dos US$ 5: a segunda sessão nem abre, a terceira também"
    )
    assert exit_code == 3, "uma rodada parada pelo orçamento não é verde nem é uma sessão reprovada"
    assert (
        "golden: budget US$ 5.00 reached at US$ 6.00; not started: P01-b, P02-c"
        in capsys.readouterr().err
    )


async def test_a_session_in_flight_when_the_budget_is_crossed_is_played_whole_and_judged(
    opened: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    judge = the_judge_answers(monkeypatch)
    sessions = _shelf(tmp_path, ("P01-a", "P01", 3), ("P01-b", "P01", 1))
    out = tmp_path / "reports"

    await golden_runner.run(_args(sessions, out, budget_usd=2.0))

    played = json.loads((out / f"P01-a.{STAMP}.json").read_text(encoding="utf-8"))
    assert [turn["idx"] for turn in played["turns"]] == [0, 1, 2], (
        "o primeiro turno de US$ 3 já passou dos US$ 2, e a sessão em curso não é cortada no meio"
    )
    assert len(judge.asked) == 1 and (out / f"P01-a.{STAMP}.verdict.json").exists(), (
        "o juiz faz parte da sessão em curso: ela termina com o veredito, e só então a rodada para"
    )
    assert opened == ["P01"]


async def test_the_last_session_crossing_the_budget_is_a_finished_run_and_not_a_stop(
    opened: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    approving = {**A_VERDICT, "scores": dict.fromkeys(A_VERDICT["scores"], 4), "incidents": []}
    the_judge_answers(monkeypatch, json.dumps(approving))
    sessions = _shelf(tmp_path, ("P01-a", "P01", 1))

    exit_code = await golden_runner.run(_args(sessions, tmp_path / "reports", budget_usd=2.0))

    assert exit_code == 0, "nada ficou por começar: a rodada que acabou além do orçamento acabou"
    assert "budget" not in capsys.readouterr().err


async def test_a_run_given_no_budget_stops_at_twenty_dollars(
    opened: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    the_judge_answers(monkeypatch)
    monkeypatch.delenv("GOLDEN_BUDGET_USD", raising=False)
    sessions = _shelf(tmp_path, ("P01-a", "P01", 7), ("P01-b", "P01", 1))

    await golden_runner.run(_args(sessions, tmp_path / "reports"))

    assert opened == ["P01"], (
        "sete turnos de US$ 3 são US$ 21, e o teto de uma rodada sem orçamento é US$ 20"
    )


async def test_the_budget_the_environment_provides_is_the_one_a_run_without_a_flag_uses(
    opened: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    the_judge_answers(monkeypatch)
    monkeypatch.setenv("GOLDEN_BUDGET_USD", "30")
    sessions = _shelf(tmp_path, ("P01-a", "P01", 7), ("P01-b", "P01", 1))

    await golden_runner.run(_args(sessions, tmp_path / "reports"))

    assert opened == ["P01", "P01"], "US$ 21 não chegam aos US$ 30 que o ambiente deu"


async def test_the_flag_beats_the_environment(
    opened: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    the_judge_answers(monkeypatch)
    monkeypatch.setenv("GOLDEN_BUDGET_USD", "100")
    sessions = _shelf(tmp_path, ("P01-a", "P01", 1), ("P01-b", "P01", 1))

    await golden_runner.run(_args(sessions, tmp_path / "reports", budget_usd=1.0))

    assert opened == ["P01"]
