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
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import text_seam
from app.core.config import get_settings
from app.services import internalization_room as room
from app.services.internalization_room import golden_judge, llm
from scripts import golden_runner
from tests.text_seam_harness import (
    A_VERDICT,
    GUIDE_LINE,
    RUNNER_KEY,
    the_app,
    the_judge_answers,
    the_models_answer,
)

BASE_URL = "http://test/api/internalization-room/text-seam/"
STAMP = "2026-09-16T18-00-00"


@pytest.fixture()
def seam_app(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        get_settings(), "internalization_room_runner_key", RUNNER_KEY, raising=False
    )
    the_models_answer(monkeypatch)
    the_judge_answers(monkeypatch)

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
        "rejudge": None,
    }
    return argparse.Namespace(**{**given, **over})


def _approving() -> dict[str, Any]:
    return {**A_VERDICT, "scores": dict.fromkeys(A_VERDICT["scores"], 4), "incidents": []}


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
    row = (
        "| P01-understand-first | FAIL | 1 | turn 1: verbatim repeat of the previous guide turn; "
        "juiz: answers_requests_to_understand 1; "
        "juiz: turn 1 · blocker · redirect_on_request_to_understand |"
    )
    assert row in readme, "a coluna mecânica é a dela: uma contagem, e o que caiu, por turno"
    assert exit_code == 1, "uma sessão recusada ou um aviso mecânico é a rodada vermelha"
    assert "0/2 golden sessions pass" in capsys.readouterr().out, (
        "passa é a regra dela: juiz aprovou e zero avisos mecânicos — uma recusa e um aviso são "
        "duas sessões que não passaram"
    )


async def test_a_played_session_is_judged_and_the_verdict_sits_beside_its_transcript(
    over_the_seam, her_sessions: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    judge = the_judge_answers(monkeypatch)
    out = tmp_path / "reports"

    await golden_runner.run(_args(her_sessions, out))

    verdict = out / f"P01-understand-first.{STAMP}.verdict.json"
    assert json.loads(verdict.read_text(encoding="utf-8")) == A_VERDICT, (
        "o JSON do juiz — notas, incidentes com turno, gravidade e citação, resumo — fica ao "
        "lado do transcript, como o dela; a lista de incidentes é o que se age em cima"
    )
    transcript = (out / f"P01-understand-first.{STAMP}.transcript.txt").read_text(encoding="utf-8")
    assert judge.asked[0]["user_content"].endswith(transcript.rstrip("\n")), (
        "o juiz lê exatamente o bloco de transcript que foi exportado"
    )


async def test_a_session_the_room_refused_after_it_played_is_not_judged(
    over_the_seam, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    judge = the_judge_answers(monkeypatch)
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    _script(sessions, "P01-kickoff-twice", "P01", [{"team": "Oi."}, {"kickoff": True}])
    out = tmp_path / "reports"

    exit_code = await golden_runner.run(_args(sessions, out))

    assert judge.asked == [], (
        "uma sessão que a sala recusou no meio não é inteira: julgá-la custa e não compara com nada"
    )
    assert not list(out.glob("*.verdict.json"))
    exported = json.loads((out / f"P01-kickoff-twice.{STAMP}.json").read_text(encoding="utf-8"))
    assert exported["refused"].startswith("409 "), (
        "a recusa vai no JSON exportado, senão um --rejudge remonta a sessão como inteira"
    )
    assert "| P01-kickoff-twice | — | recusada | 409 " in (out / "README.md").read_text(
        encoding="utf-8"
    )
    assert exit_code == 1


async def test_a_clean_run_exits_zero_and_only_the_named_session_is_played(
    over_the_seam, her_sessions: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    the_judge_answers(monkeypatch, json.dumps(_approving()))
    out = tmp_path / "reports"
    args = _args(her_sessions, out, only="P01-understand-first", turns=1)

    exit_code = await golden_runner.run(args)

    assert exit_code == 0
    assert sorted(p.name for p in out.iterdir()) == [
        f"P01-understand-first.{STAMP}.json",
        f"P01-understand-first.{STAMP}.transcript.txt",
        f"P01-understand-first.{STAMP}.verdict.json",
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
    results = [
        golden_runner.SessionResult(
            "P01-understand-first", "s-1", [first, second], verdict=_approving()
        )
    ]

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
        "(roteiros e doutrina no pin `533b6e3` · cânon `7372ec0`): **1/1 aprovadas pelo juiz, "
        "0 avisos mecânicos, 0 fail-safes em 2 turnos reais.**\n"
        "\n"
        "Este portão vale para o release, não só para o CI (DOCTRINE §5.2): nada que toque "
        "prompt, laço de turno, modelo ou tela chega à equipe sem as sessões-ouro aprovadas "
        "pelo juiz e sem aviso mecânico — uma suíte verde não basta para publicar uma mudança "
        "de prompt.\n"
        "\n"
        "| Sessão | Juiz | Mecânico | Observação |\n"
        "|---|---|---|---|\n"
        "| P01-understand-first | PASS | 0 |  |\n"
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

    assert "**0/1 aprovadas pelo juiz, 1 avisos mecânicos" in readme
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


async def test_a_session_the_judge_approved_with_a_mechanical_fault_still_does_not_pass(
    over_the_seam, her_sessions: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    the_judge_answers(monkeypatch, json.dumps(_approving()))
    out = tmp_path / "reports"

    exit_code = await golden_runner.run(_args(her_sessions, out, only="P01-understand-first"))

    assert "| P01-understand-first | PASS | 1 | turn 1: verbatim repeat" in (
        out / "README.md"
    ).read_text(encoding="utf-8")
    assert "0/1 golden sessions pass" in capsys.readouterr().out, (
        "passa é a regra dela (run.ts:206): juiz aprovou E zero avisos mecânicos"
    )
    assert exit_code == 1


async def test_a_judge_that_returns_no_verdict_fails_the_session_and_the_run_goes_on(
    over_the_seam, her_sessions: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    the_judge_answers(monkeypatch, "não é um JSON")
    out = tmp_path / "reports"

    exit_code = await golden_runner.run(_args(her_sessions, out))

    readme = (out / "README.md").read_text(encoding="utf-8")
    assert "**0/2 aprovadas pelo juiz, 1 avisos mecânicos" in readme
    assert (
        "| P01-understand-first | — | 1 | turn 1: verbatim repeat of the previous guide turn; "
        "juiz sem veredito: Expecting value: line 1 column 1 (char 0) |"
    ) in readme, "sem veredito não é aprovação nem aviso mecânico: é uma linha que diz o motivo"
    assert not list(out.glob("*.verdict.json")), "um veredito que não veio não é gravado"
    assert "FAIL · P01-understand-first · judge=n/a · mechanical=1" in capsys.readouterr().out, (
        "a linha do console é a dela: judge=n/a quando o juiz não respondeu (run.ts:208)"
    )
    assert exit_code == 1


class _Wire:
    """The provider behind the real `call_agent`, answering the judge with a priced reply."""

    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.messages = self

    async def create(self, **_: Any) -> SimpleNamespace:
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=self.reply)],
            stop_reason="end_turn",
            model="claude-fable-5-1",
            usage=SimpleNamespace(
                input_tokens=1200,
                output_tokens=400,
                cache_read_input_tokens=896000,
                cache_creation_input_tokens=0,
            ),
        )


async def test_the_judges_call_is_priced_into_the_run_beside_the_guide_and_the_validator(
    over_the_seam, her_sessions: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    monkeypatch.setattr(golden_judge, "call_agent", llm.call_agent)
    monkeypatch.setattr(llm.anthropic, "AsyncAnthropic", lambda **_: _Wire(json.dumps(A_VERDICT)))
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "sk-ant-fake")
    out = tmp_path / "reports"

    await golden_runner.run(_args(her_sessions, out, only="P01-understand-first"))

    assert (
        "Custo da rodada (linhas `[llm-usage]`, preços de tabela): ≈ US$ 0.26 — judge US$ 0.26."
    ) in (out / "README.md").read_text(encoding="utf-8"), (
        "(1200 x 10 + 400 x 50 + 896000 x 0.25) / 1e6 = 0.256, da tabela, à mão; o 5/5 dela "
        "somou o juiz junto com o Guia e o Validador"
    )
    usage_line = (
        "[llm-usage] judge claude-fable-5-1 in=1200 cache_read=896000 cache_write=0 out=400 "
        "US$ 0.256 "
    )
    assert usage_line in capsys.readouterr().out, (
        "a chamada do juiz sai na mesma linha de uso que as do turno"
    )


async def test_a_committed_run_is_judged_again_from_its_exports_without_playing_the_room(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    judge = the_judge_answers(monkeypatch)
    earlier = tmp_path / "2026-09-16"
    earlier.mkdir()
    (earlier / "P01-understand-first.2026-09-16T21-13-26.json").write_text(
        json.dumps(
            {
                "name": "P01-understand-first",
                "pericopeId": "P01",
                "language": "Brazilian Portuguese",
                "baseUrl": "http://127.0.0.1:8047/api/internalization-room/text-seam/",
                "sessionId": "s-1",
                "turns": [
                    {
                        "idx": 0,
                        "team": "Oi.",
                        "guide": GUIDE_LINE,
                        "outcome": "pass",
                        "interrupted": False,
                        "turnMs": 17000,
                        "usage": [],
                        "mechanical": [],
                    },
                    {
                        "idx": 1,
                        "team": "Explica de novo.",
                        "guide": GUIDE_LINE,
                        "outcome": "pass",
                        "interrupted": False,
                        "turnMs": 12000,
                        "usage": [],
                        "mechanical": ["verbatim repeat of the previous guide turn"],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    (earlier / "P01-kickoff-twice.2026-09-16T21-13-26.json").write_text(
        json.dumps(
            {
                "name": "P01-kickoff-twice",
                "pericopeId": "P01",
                "language": "Brazilian Portuguese",
                "baseUrl": "http://127.0.0.1:8047/api/internalization-room/text-seam/",
                "sessionId": "s-2",
                "refused": "502 o modelo não respondeu",
                "turns": [
                    {
                        "idx": 0,
                        "team": "Oi.",
                        "guide": GUIDE_LINE,
                        "outcome": "pass",
                        "interrupted": False,
                        "turnMs": 17000,
                        "usage": [],
                        "mechanical": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "2026-09-16-rejulgado"

    exit_code = await golden_runner.run(_args(earlier, out, rejudge=str(earlier)))

    assert len(judge.asked) == 1 and "| P01-kickoff-twice | — | recusada | 502 " in (
        out / "README.md"
    ).read_text(encoding="utf-8"), (
        "a sessão que a sala recusou no meio não é julgada de novo, e a linha segue recusada"
    )
    assert judge.asked[0]["user_content"].endswith(
        f"[turn 1]\nTEAM: Explica de novo.\nGUIDE (pass): {GUIDE_LINE}"
    ), "o juiz lê o mesmo bloco que a rodada original exportou, remontado do JSON"
    verdict = out / "P01-understand-first.2026-09-16T21-13-26.verdict.json"
    assert json.loads(verdict.read_text(encoding="utf-8")) == A_VERDICT, (
        "o veredito leva o carimbo da transcrição que julgou, não o de hoje"
    )
    readme = (out / "README.md").read_text(encoding="utf-8")
    assert "`http://127.0.0.1:8047/api/internalization-room/text-seam/`" in readme
    assert (
        "| P01-understand-first | FAIL | 1 | turn 1: verbatim repeat of the previous guide turn; "
        "juiz: answers_requests_to_understand 1; "
        "juiz: turn 1 · blocker · redirect_on_request_to_understand |"
    ) in readme, "a coluna mecânica vem do JSON exportado, o juiz da chamada de agora"
    assert exit_code == 1


async def test_a_rejudge_refuses_to_write_over_the_run_it_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    judge = the_judge_answers(monkeypatch)
    earlier = tmp_path / "2026-09-16"
    earlier.mkdir()
    (earlier / "README.md").write_text("o README da rodada, com o custo dela\n", encoding="utf-8")

    exit_code = await golden_runner.run(_args(earlier, earlier, rejudge=str(earlier)))

    assert exit_code == 2
    assert judge.asked == []
    assert (earlier / "README.md").read_text(encoding="utf-8") == (
        "o README da rodada, com o custo dela\n"
    ), "o README que registra o custo da rodada é o que o §5.2 amarra ao release; não se apaga"
    assert "--out" in capsys.readouterr().err


def test_the_judges_column_and_the_mechanical_column_never_read_each_other() -> None:
    warned = golden_runner.Played(idx=0, team="Oi.", guide="Vão com Deus!", outcome="pass")
    warned.mechanical = ["religious farewell of its own"]
    clean = golden_runner.Played(idx=1, team="Explica.", guide=GUIDE_LINE, outcome="pass")
    results = [
        golden_runner.SessionResult(
            "P01-spoilers-and-boundaries", "s-1", [warned], verdict=_approving()
        ),
        golden_runner.SessionResult("P01-understand-first", "s-2", [clean], verdict=A_VERDICT),
    ]

    readme = golden_runner.summary(
        results, base_url="http://test/", stamp="2026-09-16T18-00-00", tip="x", pins="p"
    )

    assert (
        "**1/2 aprovadas pelo juiz, 1 avisos mecânicos, 0 fail-safes em 2 turnos reais.**" in readme
    ), "o cabeçalho é o do README dela de 03/09: o juiz conta as suas, o mecânico as dele"
    assert (
        "| P01-spoilers-and-boundaries | PASS | 1 | turn 0: religious farewell of its own |"
        in readme
    ), "um aviso mecânico não vira reprovação do juiz"
    assert (
        "| P01-understand-first | FAIL | 0 | juiz: answers_requests_to_understand 1; "
        "juiz: turn 1 · blocker · redirect_on_request_to_understand |"
    ) in readme, (
        "uma reprovação do juiz não vira aviso mecânico — e a linha diz por que o portão fechou"
    )
