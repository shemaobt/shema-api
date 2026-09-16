"""One command plays every vendored session and leaves one report directory a person can read.

Her `npm run golden` reads `golden/sessions/`, plays each script, counts the mechanical
faults in a column of their own and prints `N/M golden sessions pass`; ours took one script
per invocation and always exited 0. The runner here is driven whole — `run(args)` opening its
own client — over the door this test mounts, the way the back-translation runner's test does.
The scripts are shaped after hers; the Jonah one is refused by this room, whose canon holds
Ruth alone, and the run has to say so and go on.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import text_seam
from app.core.config import get_settings
from app.services import internalization_room as room
from scripts import golden_runner
from tests.text_seam_harness import GUIDE_LINE, RUNNER_KEY, the_app, the_models_answer

BASE_URL = "http://test/api/internalization-room/text-seam/"
STAMP = "2026-09-16T18-00-00"


@pytest.fixture()
def seam_app(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        get_settings(), "internalization_room_runner_key", RUNNER_KEY, raising=False
    )
    the_models_answer(monkeypatch)

    async def _settled(**_: Any) -> None:
        return None

    monkeypatch.setattr(text_seam, "settle_coverage", _settled)

    async def _never_voiced(text: str, **_: Any) -> None:
        raise AssertionError(f"a costura pediu um clipe ao sintetizador: {text!r}")

    monkeypatch.setattr(room, "synthesize_facilitator_speech", _never_voiced)
    return the_app(db_session)


@pytest.fixture()
def over_the_seam(seam_app, monkeypatch: pytest.MonkeyPatch):
    made = httpx.AsyncClient

    def _client(**kwargs: Any) -> httpx.AsyncClient:
        return made(**{**kwargs, "transport": ASGITransport(app=seam_app)})

    monkeypatch.setattr(httpx, "AsyncClient", _client)


def _script(sessions: Path, name: str, pericope: str, turns: list[dict[str, Any]]) -> Path:
    path = sessions / f"{name}.json"
    path.write_text(
        json.dumps(
            {
                "name": name,
                "pericopeId": pericope,
                "language": "Brazilian Portuguese",
                "why": "shaped after hers",
                "turns": turns,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


@pytest.fixture()
def her_sessions(tmp_path: Path) -> Path:
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    _script(
        sessions,
        "P01-understand-first",
        "P01",
        [
            {"team": "Oi. A gente é a equipe Terena. Podemos começar?"},
            {
                "team": "Espera. Explica de novo o que acontece nessa passagem.",
                "expect": {"no_fail_safe": True, "no_rehearsal_invite": True},
            },
        ],
    )
    _script(
        sessions,
        "J01-frame-before-elicit",
        "J01",
        [{"kickoff": True, "expect": {"no_fail_safe": True}}],
    )
    return sessions


def _args(sessions: Path, out: Path, **over: Any) -> argparse.Namespace:
    given: dict[str, Any] = {
        "base_url": BASE_URL,
        "script": None,
        "sessions": str(sessions),
        "only": None,
        "out": str(out),
        "turns": None,
        "access_code": RUNNER_KEY,
        "stamp": STAMP,
    }
    return argparse.Namespace(**{**given, **over})


async def test_one_command_plays_every_session_and_a_refused_one_does_not_stop_the_rest(
    over_the_seam, her_sessions: Path, tmp_path: Path, capsys
) -> None:
    out = tmp_path / "reports"

    exit_code = await golden_runner.run(_args(her_sessions, out))

    played = json.loads((out / f"P01-understand-first.{STAMP}.json").read_text(encoding="utf-8"))
    assert [(t["idx"], t["guide"], t["outcome"], t["mechanical"]) for t in played["turns"]] == [
        (0, GUIDE_LINE, "pass", []),
        (1, GUIDE_LINE, "pass", ["verbatim repeat of the previous guide turn"]),
    ], "a sessão de Rute foi tocada inteira, com o check mecânico dela por turno"
    assert not list(out.glob("J01-frame-before-elicit.*")), (
        "a sessão de Jonas não abriu: este cânon só tem Rute, e nada dela é um relatório"
    )
    readme = (out / "README.md").read_text(encoding="utf-8")
    assert "| J01-frame-before-elicit | — | recusada | 400 " in readme, (
        "a recusa é uma linha do README, não o fim da rodada"
    )
    row = "| P01-understand-first | — | 1 | turn 1: verbatim repeat of the previous guide turn |"
    assert row in readme, "a coluna mecânica é a dela: uma contagem, e o que caiu, por turno"
    assert exit_code == 1, "uma sessão recusada ou um aviso mecânico é a rodada vermelha"
    assert "0/2 golden sessions pass" in capsys.readouterr().out, (
        "passa é a regra dela: juiz aprovou e zero avisos mecânicos — uma recusa e um aviso são "
        "duas sessões que não passaram"
    )


async def test_a_clean_run_exits_zero_and_only_the_named_session_is_played(
    over_the_seam, her_sessions: Path, tmp_path: Path
) -> None:
    out = tmp_path / "reports"
    args = _args(her_sessions, out, only="P01-understand-first", turns=1)

    exit_code = await golden_runner.run(args)

    assert exit_code == 0
    assert sorted(p.name for p in out.iterdir()) == [
        f"P01-understand-first.{STAMP}.json",
        f"P01-understand-first.{STAMP}.transcript.txt",
        "README.md",
    ]


def _call(role: str, cost: float | None, ms: int) -> golden_runner.Usage:
    return golden_runner.Usage(
        role=role,
        rung="claude-fable-5-1",
        input_tokens=1200,
        output_tokens=59,
        cache_read_tokens=896000,
        cache_write_tokens=0,
        latency_ms=ms,
        cost_usd=cost,
    )


def test_a_usage_line_is_spelled_the_way_hers_is_with_the_price_and_the_clock_beside() -> None:
    assert golden_runner.usage_line(_call("guide", 0.23895, 27000)) == (
        "[llm-usage] guide claude-fable-5-1 in=1200 cache_read=896000 cache_write=0 out=59 "
        "US$ 0.23895 27000 ms"
    )
    assert golden_runner.usage_line(_call("guide", None, 27000)) == (
        "[llm-usage] guide claude-fable-5-1 in=1200 cache_read=896000 cache_write=0 out=59 27000 ms"
    ), "um degrau que a tabela não precifica não é de graça: a linha sai sem o US$"


def test_the_readme_adds_the_money_up_by_role_and_times_the_voice_apart_from_the_beads() -> None:
    first = golden_runner.Played(
        idx=0,
        team="Oi.",
        guide=GUIDE_LINE,
        outcome="pass",
        turnMs=17000,
        usage=[
            _call("guide", 0.20, 10000),
            _call("validator", 0.05, 5000),
            _call("classifier", 0.01, 2000),
        ],
    )
    second = golden_runner.Played(
        idx=1,
        team="E depois?",
        guide="Depois, a família ficou em Moabe.",
        outcome="corrected",
        turnMs=33000,
        usage=[_call("guide", 0.30, 29000), _call("validator", 0.05, 4000)],
    )
    results = [golden_runner.SessionResult("P01-understand-first", "s-1", [first, second])]

    readme = golden_runner.summary(
        results,
        base_url="http://127.0.0.1:8047/api/internalization-room/text-seam/",
        stamp="2026-09-16T18-00-00",
        tip="9c4e2b34",
        pins="roteiros e doutrina no pin `533b6e3` · cânon `7372ec0`",
    )

    assert readme == (
        "# Sessões-ouro — 2026-09-16, esta sala em `9c4e2b34`, "
        "`http://127.0.0.1:8047/api/internalization-room/text-seam/`\n"
        "\n"
        "Rodada `2026-09-16T18-00-00` de `scripts/golden_runner.py` sobre os roteiros dela "
        "(roteiros e doutrina no pin `533b6e3` · cânon `7372ec0`): **1/1 sem aviso mecânico "
        "(juiz ainda não ligado), 0 avisos mecânicos, 0 fail-safes em 2 turnos reais.**\n"
        "\n"
        "| Sessão | Juiz | Mecânico | Observação |\n"
        "|---|---|---|---|\n"
        "| P01-understand-first | — | 0 |  |\n"
        "\n"
        "Custo da rodada (linhas `[llm-usage]`, preços de tabela): ≈ US$ 0.61 — classifier "
        "US$ 0.01 · guide US$ 0.50 · validator US$ 0.10.\n"
        "Latência Guia+Validador por turno: 15 a 33 s (mediana ≈ 24 s); turno inteiro, com o "
        "classificador em linha: 17 a 33 s (mediana ≈ 25 s).\n"
    ), "o README é o dela: a linha do veredito, a tabela, o dinheiro e o relógio"


def test_a_rung_the_table_never_priced_still_leaves_the_clock_in_the_readme() -> None:
    turn = golden_runner.Played(
        idx=0,
        team="Oi.",
        guide=GUIDE_LINE,
        outcome="pass",
        turnMs=17000,
        usage=[_call("guide", None, 10000), _call("validator", None, 5000)],
    )

    readme = golden_runner.summary(
        [golden_runner.SessionResult("P01-understand-first", "s-1", [turn])],
        base_url="http://test/",
        stamp="2026-09-16T18-00-00",
        tip="9c4e2b34",
        pins="pins",
    )

    assert readme.endswith(
        "A sala não informou custo por chamada nesta rodada.\n"
        "Latência Guia+Validador por turno: 15 a 15 s (mediana ≈ 15 s); turno inteiro, com o "
        "classificador em linha: 17 a 17 s (mediana ≈ 17 s).\n"
    ), "o preço e o relógio são dois campos: um degrau sem preço de tabela não apaga a latência"


def test_a_session_refused_after_it_played_keeps_its_faults_on_its_own_row() -> None:
    played = golden_runner.Played(
        idx=0, team="Oi.", guide="Vão com Deus!", outcome="pass", turnMs=17000
    )
    played.mechanical = ["religious farewell of its own"]
    refused = golden_runner.SessionResult(
        "P01-understand-first", "s-1", [played], refused="502 o modelo não respondeu"
    )

    readme = golden_runner.summary(
        [refused], base_url="http://test/", stamp="2026-09-16T18-00-00", tip="x", pins="p"
    )

    assert "**0/1 sem aviso mecânico (juiz ainda não ligado), 1 avisos mecânicos" in readme
    assert (
        "| P01-understand-first | — | recusada · 1 | 502 o modelo não respondeu; "
        "turn 0: religious farewell of its own |"
    ) in readme, "o cabeçalho contava um aviso que nenhuma linha da tabela mostrava"


def test_a_call_the_table_never_priced_is_counted_out_loud_beside_the_total() -> None:
    unpriced = _call("guide", None, 10000)
    unpriced.rung = "claude-opus-6"
    turn = golden_runner.Played(
        idx=0,
        team="Oi.",
        guide=GUIDE_LINE,
        outcome="pass",
        turnMs=17000,
        usage=[unpriced, _call("validator", 0.05, 5000)],
    )

    readme = golden_runner.summary(
        [golden_runner.SessionResult("P01-understand-first", "s-1", [turn])],
        base_url="http://test/",
        stamp="2026-09-16T18-00-00",
        tip="x",
        pins="p",
    )

    assert (
        "Custo da rodada (linhas `[llm-usage]`, preços de tabela): ≈ US$ 0.05 — validator "
        "US$ 0.05; 1 chamada sem preço de tabela (claude-opus-6), fora da soma.\n"
    ) in readme, "uma chamada sem preço saía da soma como se fosse de graça, sem uma palavra"
