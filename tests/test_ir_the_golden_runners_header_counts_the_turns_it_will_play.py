"""The Guide-turn runner's session header says how many turns it is about to play.

`--turns` cuts every script short, so the person reading the console has only the header to tell
a cut run from a whole one. The room is a wire this test owns and the judge is a double.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from scripts import golden_runner
from tests.golden_spend_harness import (
    GOLDEN_PRICED,
    golden_args,
    golden_shelf,
    the_room_answers,
)
from tests.text_seam_harness import A_VERDICT, GUIDE_LINE, the_judge_answers


def _a_room_that_plays_and_a_judge_that_approves(monkeypatch: pytest.MonkeyPatch) -> None:
    approving = {**A_VERDICT, "scores": dict.fromkeys(A_VERDICT["scores"], 4), "incidents": []}
    the_judge_answers(monkeypatch, json.dumps(approving))

    def _room(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/golden/session"):
            return httpx.Response(200, json={"sessionId": "s-1"})
        return httpx.Response(
            200, json={"guideText": GUIDE_LINE, "outcome": "pass", "usage": GOLDEN_PRICED}
        )

    the_room_answers(monkeypatch, _room)


async def test_a_run_cut_short_says_how_many_of_the_scripts_turns_it_will_play(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    _a_room_that_plays_and_a_judge_that_approves(monkeypatch)
    sessions = golden_shelf(tmp_path, ("P01-a", "P01", 10))

    await golden_runner.run(golden_args(sessions, tmp_path / "reports", turns=3))

    printed = capsys.readouterr().out
    assert "\n▶ P01-a (P01, Brazilian Portuguese) — 3 of 10 turns\n" in printed, (
        "o cabeçalho dizia 10 turns com --turns 3, e quem lia não via que a rodada era cortada"
    )


@pytest.mark.parametrize(
    ("in_the_script", "asked_for", "header_ends"),
    [
        (10, None, "— 10 turns\n"),
        (10, 10, "— 10 turns\n"),
        (10, 20, "— 10 turns\n"),
        (0, 3, "— 0 turns\n"),
        (1, None, "— 1 turns\n"),
    ],
)
async def test_a_run_that_plays_the_whole_script_prints_the_header_it_always_printed(
    in_the_script: int,
    asked_for: int | None,
    header_ends: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    _a_room_that_plays_and_a_judge_that_approves(monkeypatch)
    sessions = golden_shelf(tmp_path, ("P01-a", "P01", in_the_script))

    await golden_runner.run(golden_args(sessions, tmp_path / "reports", turns=asked_for))

    assert f"\n▶ P01-a (P01, Brazilian Portuguese) {header_ends}" in capsys.readouterr().out, (
        "uma rodada inteira não é cortada: o cabeçalho não ganha um «of» que ela não tem"
    )
