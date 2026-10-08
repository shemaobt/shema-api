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
from tests.golden_spend_harness import charged_call, the_room_answers
from tests.text_seam_harness import A_VERDICT, GUIDE_LINE, RUNNER_KEY, the_judge_answers

STAMP = "2026-10-08T12-00-00"


PRICED = [charged_call("guide", 2.0), charged_call("validator", 1.0)]
WITH_ONE_UNPRICED = [*PRICED, charged_call("classifier", None, input_tokens=0, output_tokens=0)]


def _room_charging(monkeypatch: pytest.MonkeyPatch, usage: list[dict[str, Any]]) -> list[str]:
    sessions: list[str] = []

    def _room(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/golden/session"):
            sessions.append(json.loads(request.content)["pericopeId"])
            return httpx.Response(200, json={"sessionId": f"s-{len(sessions)}"})
        return httpx.Response(
            200, json={"guideText": GUIDE_LINE, "outcome": "pass", "usage": usage}
        )

    the_room_answers(monkeypatch, _room)
    return sessions


@pytest.fixture()
def opened(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    return _room_charging(monkeypatch, PRICED)


@pytest.fixture()
def opened_with_a_call_the_table_never_priced(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    return _room_charging(monkeypatch, WITH_ONE_UNPRICED)


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
    approving = {**A_VERDICT, "scores": dict.fromkeys(A_VERDICT["scores"], 4), "incidents": []}
    the_judge_answers(monkeypatch, json.dumps(approving))
    sessions = _shelf(tmp_path, ("P01-a", "P01", 1), ("P01-b", "P01", 1), ("P02-c", "P02", 1))

    exit_code = await golden_runner.run(_args(sessions, tmp_path / "reports", budget_usd=2.0))

    assert opened == ["P01"], (
        "um turno de US$ 3 passa dos US$ 2: a segunda sessão nem abre, a terceira também"
    )
    assert exit_code == 3, "uma rodada parada pelo orçamento não é verde nem é uma sessão reprovada"
    assert (
        "golden: budget US$ 2.00 reached at US$ 3.00; not started: P01-b, P02-c"
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


async def test_each_sessions_line_shows_what_it_cost_and_the_run_ends_with_the_total_by_role(
    opened: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    approving = {**A_VERDICT, "scores": dict.fromkeys(A_VERDICT["scores"], 4), "incidents": []}
    the_judge_answers(monkeypatch, json.dumps(approving))
    sessions = _shelf(tmp_path, ("P01-a", "P01", 1), ("P02-b", "P02", 2))

    await golden_runner.run(_args(sessions, tmp_path / "reports", budget_usd=100.0))

    shown = capsys.readouterr().out
    assert "  PASS · P01-a · judge=pass · mechanical=0 · cost US$ 3.00\n" in shown, (
        "uma volta de US$ 2 do Guia e US$ 1 do Validador custa US$ 3"
    )
    assert "  FAIL · P02-b · judge=pass · mechanical=1 · cost US$ 6.00\n" in shown
    assert "\ncost US$ 9.00 — guide US$ 6.00 · validator US$ 3.00\n" in shown, (
        "a rodada termina com o total e a divisão por papel, na tela e não só no README"
    )


async def test_the_total_and_the_stop_say_how_many_calls_the_budget_could_not_see(
    opened_with_a_call_the_table_never_priced: list[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    the_judge_answers(monkeypatch)
    sessions = _shelf(tmp_path, ("P01-a", "P01", 2), ("P01-b", "P01", 1))

    await golden_runner.run(_args(sessions, tmp_path / "reports", budget_usd=5.0))

    shown = capsys.readouterr()
    assert (
        "golden: budget US$ 5.00 reached at US$ 6.00; not started: P01-b; "
        "2 calls had no table price; the budget counted them at the highest table price\n"
    ) in shown.err, "um modelo fora da tabela não pode furar o teto sem que ninguém seja avisado"
    assert (
        "\ncost US$ 6.00 — guide US$ 4.00 · validator US$ 2.00; "
        "2 calls had no table price; the budget counted them at the highest table price\n"
    ) in shown.out


async def test_one_call_the_budget_could_not_see_is_a_call_and_not_calls(
    opened_with_a_call_the_table_never_priced: list[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    the_judge_answers(monkeypatch)
    sessions = _shelf(tmp_path, ("P01-a", "P01", 1))

    await golden_runner.run(_args(sessions, tmp_path / "reports", budget_usd=100.0))

    assert (
        "1 call had no table price; the budget counted it at the highest table price\n"
        in capsys.readouterr().out
    )


async def test_the_readme_of_a_stopped_run_says_it_stopped_and_names_what_it_left(
    opened: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    the_judge_answers(monkeypatch)
    sessions = _shelf(tmp_path, ("P01-a", "P01", 2), ("P01-b", "P01", 1), ("P02-c", "P02", 1))
    out = tmp_path / "reports"

    await golden_runner.run(_args(sessions, out, budget_usd=5.0))

    assert (
        "Rodada parada pelo orçamento de US$ 5.00, já em US$ 6.00. "
        "Sessões que não começaram: P01-b, P02-c.\n"
    ) in (out / "README.md").read_text(encoding="utf-8"), (
        "um README de 1/1 sem esta linha passaria por uma rodada inteira"
    )


def _earlier_run(directory: Path, *names: str) -> Path:
    directory.mkdir()
    for name in names:
        (directory / f"{name}.2026-10-07T21-13-26.json").write_text(
            json.dumps(
                {
                    "name": name,
                    "pericopeId": "P01",
                    "language": "Brazilian Portuguese",
                    "baseUrl": "http://room/api/internalization-room/",
                    "sessionId": f"s-{name}",
                    "turns": [
                        {
                            "idx": 0,
                            "team": "Oi.",
                            "guide": GUIDE_LINE,
                            "outcome": "pass",
                            "interrupted": False,
                            "turnMs": 1000,
                            "usage": [],
                            "mechanical": [],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
    return directory


async def test_a_rejudge_counts_its_judge_calls_and_stops_before_the_export_it_cannot_afford(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    judged: list[str] = []

    async def _judge_that_charges(script, result, *, out, stamp, prompt_repeats) -> None:
        judged.append(script.name)
        result.judge_usage = [golden_runner.Usage("judge", "claude-fable-5-1", 1, 1, 0, 0, 1, 3.0)]
        result.verdict = {
            **A_VERDICT,
            "scores": dict.fromkeys(A_VERDICT["scores"], 4),
            "incidents": [],
        }

    monkeypatch.setattr(golden_runner, "judge", _judge_that_charges)
    earlier = _earlier_run(tmp_path / "earlier", "P01-a", "P01-b", "P01-c")
    out = tmp_path / "rejudged"

    exit_code = await golden_runner.run(_args(earlier, out, rejudge=str(earlier), budget_usd=2.0))

    assert judged == ["P01-a"], "a primeira chamada do juiz, US$ 3, já passou dos US$ 2"
    assert exit_code == 3
    assert (
        "golden: budget US$ 2.00 reached at US$ 3.00; not started: P01-b, P01-c"
        in capsys.readouterr().err
    )
    assert (
        "Rodada parada pelo orçamento de US$ 2.00, já em US$ 3.00. "
        "Sessões que não começaram: P01-b, P01-c.\n"
    ) in (out / "README.md").read_text(encoding="utf-8")


async def test_a_session_that_failed_keeps_the_gates_one_when_the_budget_then_stops_the_run(
    opened: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    the_judge_answers(monkeypatch)
    sessions = _shelf(tmp_path, ("P01-a", "P01", 1), ("P01-b", "P01", 1))

    exit_code = await golden_runner.run(_args(sessions, tmp_path / "reports", budget_usd=2.0))

    assert exit_code == 1, (
        "a sessão reprovada é o portão: o 3 só diz que a rodada parou e que nada mais deu errado"
    )
    assert "not started: P01-b" in capsys.readouterr().err, "e a frase da parada sai do mesmo jeito"


async def test_an_unpriced_rung_is_budgeted_at_the_dearest_price_and_still_stops_the_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    unpriced = [charged_call("guide", None, input_tokens=1_000_000, output_tokens=100_000)]
    opened = _room_charging(monkeypatch, unpriced)
    the_judge_answers(monkeypatch)
    sessions = _shelf(tmp_path, ("P01-a", "P01", 1), ("P01-b", "P01", 1))

    await golden_runner.run(_args(sessions, tmp_path / "reports", budget_usd=5.0))

    shown = capsys.readouterr()
    assert opened == ["P01"], (
        "um milhão de tokens de entrada a US$ 10 e cem mil de saída a US$ 50 por milhão são "
        "US$ 15, e uma rodada cega ao próprio modelo não pode seguir como se fosse de graça"
    )
    sentence = "1 call had no table price; the budget counted it at the highest table price"
    assert f"reached at US$ 15.00; not started: P01-b; {sentence}\n" in shown.err
    assert f"\ncost US$ 0.00; {sentence}\n" in shown.out, (
        "o total diz o aviso mesmo quando nenhuma chamada teve preço"
    )


async def test_an_unpriced_rungs_cache_tokens_are_budgeted_at_the_dearest_read_and_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    unpriced = [
        charged_call(
            "guide",
            None,
            input_tokens=0,
            output_tokens=0,
            cache_read_tokens=1_000_000,
            cache_write_tokens=100_000,
        )
    ]
    opened = _room_charging(monkeypatch, unpriced)
    the_judge_answers(monkeypatch)
    sessions = _shelf(tmp_path, ("P01-a", "P01", 1), ("P01-b", "P01", 1))

    await golden_runner.run(_args(sessions, tmp_path / "reports", budget_usd=2.4))

    assert opened == ["P01"]
    assert "reached at US$ 2.50;" in capsys.readouterr().err, (
        "um milhão lido a US$ 0.50 e cem mil escritos por uma hora a US$ 20 são US$ 2.50, "
        "os preços mais altos da tabela para cada tipo de token de cache"
    )
