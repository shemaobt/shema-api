"""The back-translation runner says what happened when a run has nothing to play, or dies midway.

The sibling of the Guide-turn runner's test, one door along: a shelf with no script on it, the
room turning one script away before its first round, and an error that is not the room's
refusal killing a script between rounds. The room is a wire this test owns, so the money and
the failure are its own arithmetic.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest

from scripts import bt_golden_runner
from tests.golden_spend_harness import BT_PRICED, bt_args, bt_shelf, charged_call, the_room_answers


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


async def test_a_script_that_cannot_be_read_is_named_and_the_run_pays_for_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    asked: list[str] = []

    def _room(request: httpx.Request) -> httpx.Response:
        asked.append(request.url.path)
        return httpx.Response(500)

    the_room_answers(monkeypatch, _room)
    bt_shelf(tmp_path, monkeypatch, ("P01-a", "P01", 1), ("P02-b", "P02", 1))
    broken = tmp_path / "bt" / "P02-b.json"
    broken.write_text('{"name": "P02-b", "pericopeId": "P02"', encoding="utf-8")

    exit_code = await bt_golden_runner.run(bt_args(tmp_path / "reports"))

    assert exit_code == 2, "um roteiro ilegível não é um check reprovado: a rodada nem começa"
    assert capsys.readouterr().err.startswith(f"bt golden: {broken}: JSONDecodeError: "), (
        "o JSON cortado derrubava os roteiros seguintes num traceback sem o nome do arquivo"
    )
    assert asked == [], "o P01 estava bom, mas a rodada com um roteiro ruim não gasta nada"


async def test_a_script_named_by_a_path_that_does_not_exist_is_named_back(
    tmp_path: Path, capsys
) -> None:
    gone = tmp_path / "gone.json"

    exit_code = await bt_golden_runner.run(bt_args(tmp_path / "reports", script=str(gone)))

    assert exit_code == 2
    assert capsys.readouterr().err.startswith(f"bt golden: {gone}: FileNotFoundError: "), (
        "quem passou --script com o caminho errado levava um traceback sem o caminho de volta"
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


async def test_a_script_killed_by_a_timeout_is_a_killed_verdict_naming_the_error_and_never_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    rounds: list[str] = []

    def _room(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/session"):
            return httpx.Response(200, json={"sessionId": "s-1"})
        rounds.append(request.url.path)
        if len(rounds) == 2:
            raise httpx.ReadTimeout("the room did not answer", request=request)
        return _a_round_that_costs_three_dollars()

    the_room_answers(monkeypatch, _room)
    bt_shelf(tmp_path, monkeypatch, ("P01-a", "P01", 2))

    with pytest.raises(httpx.ReadTimeout):
        await bt_golden_runner.run(bt_args(tmp_path / "reports"))

    shown = capsys.readouterr().out
    assert (
        "  KILLED · ReadTimeout: the room did not answer · 0 check(s) failed · s-1 "
        "· cost US$ 3.00\n"
    ) in shown, "o roteiro morreu na segunda rodada e a linha dele dizia PASS"
    assert "PASS" not in shown


async def test_a_room_that_reports_usage_in_another_shape_is_a_key_error_on_the_round_it_arrives(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rounds: list[str] = []
    older = {
        key: value for key, value in charged_call("analyst", 2.0).items() if key != "latency_ms"
    }

    def _room(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/session"):
            return httpx.Response(200, json={"sessionId": "s-1"})
        rounds.append(request.url.path)
        return httpx.Response(
            200,
            json={
                "findings": [],
                "spoken": "Muito bem.",
                "outcome": "pass",
                "conferida": True,
                "missingWithoutFrase": 0,
                "usage": [older],
            },
        )

    the_room_answers(monkeypatch, _room)
    bt_shelf(tmp_path, monkeypatch, ("P01-a", "P01", 2))

    with pytest.raises(KeyError, match="latency_ms"):
        await bt_golden_runner.run(bt_args(tmp_path / "reports"))

    assert len(rounds) == 1, (
        "uma sala mais velha que a costura pagava todas as rodadas e só estourava na conta"
    )


async def test_a_script_the_room_could_not_be_reached_to_open_is_a_killed_verdict_too(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    opened: list[str] = []

    def _room(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/session"):
            pericope = json.loads(request.content)["pericopeId"]
            opened.append(pericope)
            if pericope == "P02":
                raise httpx.ConnectError("the room is restarting", request=request)
            return httpx.Response(200, json={"sessionId": f"s-{pericope}"})
        return _a_round_that_costs_three_dollars()

    the_room_answers(monkeypatch, _room)
    bt_shelf(tmp_path, monkeypatch, ("P01-a", "P01", 1), ("P02-b", "P02", 1), ("P03-c", "P03", 1))

    with pytest.raises(httpx.ConnectError):
        await bt_golden_runner.run(bt_args(tmp_path / "reports"))

    shown = capsys.readouterr().out
    assert "  KILLED · ConnectError: the room is restarting · P02-b not opened\n" in shown, (
        "a sala reiniciou na porta do segundo roteiro e a rodada morria sem uma linha dele"
    )
    assert "\ncost US$ 3.00 — analyst US$ 2.00 · speaker US$ 1.00\n" in shown
    assert opened == ["P01", "P02"], "a rodada morta não tenta o terceiro roteiro"


async def test_a_script_cancelled_midway_is_a_killed_verdict_naming_the_cancel_and_never_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    rounds: list[str] = []
    silent = asyncio.Event()

    async def _room(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/session"):
            return httpx.Response(200, json={"sessionId": "s-1"})
        rounds.append(request.url.path)
        if len(rounds) == 2:
            silent.set()
            await asyncio.Event().wait()
        return _a_round_that_costs_three_dollars()

    the_room_answers(monkeypatch, _room)
    bt_shelf(tmp_path, monkeypatch, ("P01-a", "P01", 2))
    playing = asyncio.create_task(bt_golden_runner.run(bt_args(tmp_path / "reports")))
    await silent.wait()

    playing.cancel()

    with pytest.raises(asyncio.CancelledError):
        await playing
    shown = capsys.readouterr().out
    assert "  KILLED · CancelledError · 0 check(s) failed · s-1 · cost US$ 3.00\n" in shown, (
        "o Ctrl-C cancelou o roteiro na segunda rodada e a linha dele dizia PASS"
    )
    assert "PASS" not in shown
    assert "\ncost US$ 3.00 — analyst US$ 2.00 · speaker US$ 1.00\n" in shown
