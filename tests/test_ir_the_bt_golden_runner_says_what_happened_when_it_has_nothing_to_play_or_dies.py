"""The back-translation runner says what happened when a run has nothing to play, or dies midway.

The sibling of the Guide-turn runner's test, one door along: a shelf with no script on it, the
room turning one script away before its first round, and an error that is not the room's
refusal killing a script between rounds. The room is a wire this test owns, so the money and
the failure are its own arithmetic.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pytest

from scripts import bt_golden_runner

BASE_URL = "http://room/api/internalization-room/text-seam/back-translation/"


def _args(out: Path, **over: Any) -> argparse.Namespace:
    given: dict[str, Any] = {
        "base_url": BASE_URL,
        "script": None,
        "out": str(out),
        "access_code": "runner-de-teste",
        "budget_usd": None,
    }
    return argparse.Namespace(**{**given, **over})


async def test_an_empty_shelf_exits_with_a_message_and_not_a_value_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    shelf = tmp_path / "bt"
    shelf.mkdir()
    monkeypatch.setattr(bt_golden_runner, "BT_DIR", shelf)

    exit_code = await bt_golden_runner.run(_args(tmp_path / "reports"))

    assert exit_code == 2
    assert capsys.readouterr().err == f"bt golden: no script under {shelf}\n", (
        "uma estante vazia estourava um ValueError de max() sobre nenhum código de saída"
    )
