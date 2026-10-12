"""The Guide-turn runner says what happened when a run has nothing to play, or dies midway.

Two ways a run ends that no session of hers describes: the sessions directory holds nothing to
play, and an error that is not the room's refusal kills it between one turn and the next. The
room is a wire this test owns, so the money and the failure are its own arithmetic.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from scripts import golden_runner
from tests.golden_spend_harness import charged_call, the_room_answers
from tests.text_seam_harness import A_VERDICT, GUIDE_LINE, RUNNER_KEY, the_judge_answers

STAMP = "2026-10-12T12-00-00"

PRICED = [charged_call("guide", 2.0), charged_call("validator", 1.0)]


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


async def test_a_session_asked_for_by_name_that_the_shelf_does_not_hold_is_named_back(
    tmp_path: Path, capsys
) -> None:
    sessions = _shelf(tmp_path, ("P01-a", "P01", 1))

    exit_code = await golden_runner.run(_args(sessions, tmp_path / "reports", only="P09-not-there"))

    assert exit_code == 2
    assert capsys.readouterr().err == "golden: no session named P09-not-there\n", (
        "quem pediu P09-not-there precisa ler esse nome de volta, e não o de outra sessão"
    )


async def test_an_empty_sessions_directory_names_the_directory_and_not_a_session(
    tmp_path: Path, capsys
) -> None:
    sessions = _shelf(tmp_path)

    exit_code = await golden_runner.run(_args(sessions, tmp_path / "reports"))

    assert exit_code == 2
    assert capsys.readouterr().err == f"golden: no sessions under {sessions}\n", (
        "a pasta vazia dizia «no session named None», como se alguém tivesse pedido uma sessão"
    )


async def test_a_session_killed_by_a_timeout_still_leaves_the_readme_and_the_cost_total(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    approving = {**A_VERDICT, "scores": dict.fromkeys(A_VERDICT["scores"], 4), "incidents": []}
    the_judge_answers(monkeypatch, json.dumps(approving))
    turns: list[str] = []

    def _room(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/golden/session"):
            return httpx.Response(200, json={"sessionId": "s-1"})
        turns.append(request.url.path)
        if len(turns) == 3:
            raise httpx.ReadTimeout("the room did not answer", request=request)
        return httpx.Response(
            200, json={"guideText": GUIDE_LINE, "outcome": "pass", "usage": PRICED}
        )

    the_room_answers(monkeypatch, _room)
    sessions = _shelf(tmp_path, ("P01-a", "P01", 1), ("P02-b", "P02", 2))
    out = tmp_path / "reports"

    with pytest.raises(httpx.ReadTimeout):
        await golden_runner.run(_args(sessions, out))

    readme = (out / "README.md").read_text(encoding="utf-8")
    assert "| P01-a | PASS |" in readme and "| P02-b | — |" in readme, (
        "o P01 foi jogado e julgado, o P02 morreu no segundo turno sem juiz: as duas linhas existem"
    )
    assert "≈ US$ 6.00 — guide US$ 4.00 · validator US$ 2.00." in readme, (
        "dois turnos foram pagos, um em cada sessão, e a sessão que morreu entra na conta"
    )
    assert "Rodada interrompida por ReadTimeout: the room did not answer.\n" in readme
    assert "\ncost US$ 6.00 — guide US$ 4.00 · validator US$ 2.00\n" in capsys.readouterr().out
