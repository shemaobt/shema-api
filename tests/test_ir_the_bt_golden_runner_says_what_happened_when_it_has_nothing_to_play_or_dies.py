"""The back-translation runner says what happened when a run has nothing to play, or dies midway.

The sibling of the Guide-turn runner's test, one door along: a shelf with no script on it, the
room turning one script away before its first round, and an error that is not the room's
refusal killing a script between rounds. The room is a wire this test owns, so the money and
the failure are its own arithmetic.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from scripts import bt_golden_runner
from tests.golden_spend_harness import BT_PRICED, bt_args, bt_shelf, the_room_answers


def _a_round_that_costs_three_dollars() -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "findings": [],
            "spoken": "Vocês disseram tudo na tradução. Muito bem.",
            "outcome": "pass",
            "conferida": True,
            "missingWithoutFrase": 0,
            "usage": BT_PRICED,
        },
    )


async def test_an_empty_shelf_exits_with_a_message_and_not_a_value_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    shelf = tmp_path / "bt"
    shelf.mkdir()
    monkeypatch.setattr(bt_golden_runner, "BT_DIR", shelf)

    exit_code = await bt_golden_runner.run(bt_args(tmp_path / "reports"))

    assert exit_code == 2
    assert capsys.readouterr().err == f"bt golden: no script under {shelf}\n", (
        "uma estante vazia estourava um ValueError de max() sobre nenhum código de saída"
    )


async def test_the_room_turning_one_script_away_keeps_what_the_earlier_ones_cost(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    asked: list[str] = []

    def _room(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/session"):
            pericope = json.loads(request.content)["pericopeId"]
            asked.append(pericope)
            if pericope == "P02":
                return httpx.Response(403, text="this canon does not hold P02")
            return httpx.Response(200, json={"sessionId": f"s-{pericope}"})
        return _a_round_that_costs_three_dollars()

    the_room_answers(monkeypatch, _room)
    bt_shelf(tmp_path, monkeypatch, ("P01-a", "P01", 1), ("P02-b", "P02", 1), ("P03-c", "P03", 1))

    exit_code = await bt_golden_runner.run(bt_args(tmp_path / "reports"))

    shown = capsys.readouterr()
    assert exit_code == 2, "a sala recusar um roteiro não é um check reprovado: é o 2 do runner"
    assert asked == ["P01", "P02", "P03"], (
        "o erro ao abrir o segundo roteiro derrubava a rodada e o terceiro nem era tentado"
    )
    assert "bt golden: 403 this canon does not hold P02\n" in shown.err
    assert "\ncost US$ 6.00 — analyst US$ 4.00 · speaker US$ 2.00\n" in shown.out, (
        "o P01 e o P03 custaram US$ 3 cada, e o P02 não chegou a custar nada: a conta não se perde"
    )


async def test_a_script_killed_by_a_timeout_still_leaves_the_run_its_cost_total(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    rounds: list[str] = []

    def _room(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/session"):
            return httpx.Response(200, json={"sessionId": "s-1"})
        rounds.append(request.url.path)
        if len(rounds) == 3:
            raise httpx.ReadTimeout("the room did not answer", request=request)
        return _a_round_that_costs_three_dollars()

    the_room_answers(monkeypatch, _room)
    bt_shelf(tmp_path, monkeypatch, ("P01-a", "P01", 1), ("P02-b", "P02", 2))

    with pytest.raises(httpx.ReadTimeout):
        await bt_golden_runner.run(bt_args(tmp_path / "reports"))

    assert "\ncost US$ 6.00 — analyst US$ 4.00 · speaker US$ 2.00\n" in capsys.readouterr().out, (
        "uma rodada de cada roteiro foi paga antes de o tempo esgotar, e a conta não aparecia"
    )
