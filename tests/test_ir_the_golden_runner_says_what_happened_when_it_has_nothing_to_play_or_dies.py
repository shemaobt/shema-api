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

from scripts import golden_runner
from tests.text_seam_harness import RUNNER_KEY

STAMP = "2026-10-12T12-00-00"


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
