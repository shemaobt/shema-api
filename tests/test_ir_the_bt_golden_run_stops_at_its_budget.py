"""A back-translation golden run that has spent its budget starts no further script.

The sibling of the Guide-turn runner's budget, one door along: the same ceiling from the same
three sources, the same exit and the same sentence on stderr. The room is a wire that charges a
known price per round, so the money is the test's own arithmetic.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from scripts import bt_golden_runner
from tests.golden_spend_harness import charged_call, the_room_answers

BASE_URL = "http://room/api/internalization-room/text-seam/back-translation/"

PRICED = [charged_call("analyst", 2.0), charged_call("speaker", 1.0)]
WITH_ONE_UNPRICED = [*PRICED, charged_call("classifier", None)]


def _room_charging(monkeypatch: pytest.MonkeyPatch, usage: list[dict[str, Any]]) -> list[str]:
    sessions: list[str] = []

    def _room(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/session"):
            sessions.append(json.loads(request.content)["pericopeId"])
            return httpx.Response(200, json={"sessionId": f"s-{len(sessions)}"})
        return httpx.Response(
            200,
            json={
                "findings": [],
                "spoken": "Vocês disseram tudo na tradução. Muito bem.",
                "outcome": "pass",
                "conferida": True,
                "missingWithoutFrase": 0,
                "usage": usage,
            },
        )

    the_room_answers(monkeypatch, _room)
    return sessions


@pytest.fixture()
def opened(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    return _room_charging(monkeypatch, PRICED)


@pytest.fixture()
def opened_with_a_call_the_table_never_priced(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    return _room_charging(monkeypatch, WITH_ONE_UNPRICED)


def _shelf(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *scripts: tuple[str, str, int]) -> None:
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
                            "expect": {"conferida": True, "findings": []},
                        }
                        for _ in range(rounds)
                    ],
                }
            ),
            encoding="utf-8",
        )
    monkeypatch.setattr(bt_golden_runner, "BT_DIR", shelf)


def _args(out: Path, **over: Any) -> argparse.Namespace:
    given: dict[str, Any] = {
        "base_url": BASE_URL,
        "script": None,
        "out": str(out),
        "access_code": "runner-de-teste",
        "budget_usd": None,
    }
    return argparse.Namespace(**{**given, **over})


async def test_a_run_past_its_budget_starts_no_further_script_and_names_them(
    opened: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    _shelf(tmp_path, monkeypatch, ("P01-a", "P01", 2), ("P02-b", "P02", 1), ("P02-c", "P02", 1))
    out = tmp_path / "reports"

    exit_code = await bt_golden_runner.run(_args(out, budget_usd=5.0))

    assert opened == ["P01"], (
        "duas rodadas de US$ 3 passam dos US$ 5: o segundo roteiro nem declara sessão"
    )
    assert exit_code == 3, "uma rodada parada pelo orçamento não é verde nem um check reprovado"
    assert (
        "bt golden: budget US$ 5.00 reached at US$ 6.00; not started: P02-b, P02-c"
        in capsys.readouterr().err
    )
    played = json.loads(next(out.glob("P01-a.*.json")).read_text(encoding="utf-8"))
    assert [one["idx"] for one in played["rounds"]] == [0, 1], (
        "o roteiro em curso termina as suas rodadas antes de a rodada parar"
    )


async def test_each_scripts_line_shows_what_it_cost_and_the_run_ends_with_the_total_by_role(
    opened: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    _shelf(tmp_path, monkeypatch, ("P01-a", "P01", 1), ("P02-b", "P02", 2))

    await bt_golden_runner.run(_args(tmp_path / "reports", budget_usd=100.0))

    shown = capsys.readouterr().out
    assert "  PASS · 0 check(s) failed · s-1 · cost US$ 3.00\n" in shown, (
        "uma rodada de US$ 2 do analista e US$ 1 da voz custa US$ 3"
    )
    assert "  PASS · 0 check(s) failed · s-2 · cost US$ 6.00\n" in shown
    assert "\ncost US$ 9.00 — analyst US$ 6.00 · speaker US$ 3.00\n" in shown, (
        "a rodada termina com o total e a divisão por papel"
    )


async def test_the_total_and_the_stop_say_how_many_calls_the_budget_could_not_see(
    opened_with_a_call_the_table_never_priced: list[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    _shelf(tmp_path, monkeypatch, ("P01-a", "P01", 2), ("P02-b", "P02", 1))

    await bt_golden_runner.run(_args(tmp_path / "reports", budget_usd=5.0))

    shown = capsys.readouterr()
    assert (
        "bt golden: budget US$ 5.00 reached at US$ 6.00; not started: P02-b; "
        "the budget did not count 2 calls with no price\n"
    ) in shown.err
    assert (
        "\ncost US$ 6.00 — analyst US$ 4.00 · speaker US$ 2.00; "
        "the budget did not count 2 calls with no price\n"
    ) in shown.out


async def test_a_run_given_no_budget_stops_at_twenty_dollars(
    opened: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("GOLDEN_BUDGET_USD", raising=False)
    _shelf(tmp_path, monkeypatch, ("P01-a", "P01", 7), ("P02-b", "P02", 1))

    await bt_golden_runner.run(_args(tmp_path / "reports"))

    assert opened == ["P01"], "sete rodadas de US$ 3 são US$ 21, e o teto sem orçamento é US$ 20"


async def test_the_budget_the_environment_provides_is_the_one_a_run_without_a_flag_uses(
    opened: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GOLDEN_BUDGET_USD", "30")
    _shelf(tmp_path, monkeypatch, ("P01-a", "P01", 7), ("P02-b", "P02", 1))

    await bt_golden_runner.run(_args(tmp_path / "reports"))

    assert opened == ["P01", "P02"], "US$ 21 não chegam aos US$ 30 que o ambiente deu"
