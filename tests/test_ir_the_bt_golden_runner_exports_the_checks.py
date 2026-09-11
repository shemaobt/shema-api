"""The back-translation golden runner: her script in, her verdict and our report out.

The sibling of `scripts/golden_runner.py`, one door along. It reads one of her
`golden/bt/*.json` verbatim, declares the session over her clips, plays each round of frases
as text, judges the result with her own checks and writes the report a person reads beside
one of hers. The exit code is the gate: 1 when any check failed, 2 on an HTTP error, 0 clean.
"""

from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.services import internalization_room as room
from scripts import bt_golden_runner
from scripts.bt_golden_runner import export, load_script, open_session, play
from tests.test_ir_the_text_seam_hears_a_telling_back import (
    RUNNER_KEY,
    THE_EXTRA_CAUSE,
    Analyst,
    Speaker,
    _the_app,
)

BASE_URL = "http://test/api/internalization-room/text-seam/back-translation/"

HER_EXPECTATION: dict[str, Any] = {
    "conferida": False,
    "findings": [
        {
            "kind": "addition",
            "note": "(?=[\\s\\S]*noras?)(?=[\\s\\S]*pedi)(?=[\\s\\S]*(decid|volt))",
            "frase": 1,
        }
    ],
    "no_kinds": ["missing"],
    "spoken_names_frase": 1,
    "spoken_asks_audio_or_explanation": True,
}


@pytest.fixture()
def analyst(monkeypatch: pytest.MonkeyPatch) -> Analyst:
    from app.services.internalization_room import back_translation as bt_service

    reader = Analyst()
    reader.readings = [{"findings": [{"kind": "addition", "note": THE_EXTRA_CAUSE, "chunk": 1}]}]
    monkeypatch.setattr(bt_service, "call_agent", reader)
    return reader


@pytest.fixture()
def speaker(monkeypatch: pytest.MonkeyPatch) -> Speaker:
    turn_module = importlib.import_module("app.services.internalization_room.run_turn")

    voice = Speaker()
    monkeypatch.setattr(turn_module, "call_agent", voice)
    return voice


@pytest.fixture()
def seam_app(
    db_session: AsyncSession,
    analyst: Analyst,
    speaker: Speaker,
    monkeypatch: pytest.MonkeyPatch,
):
    """The door itself, with the key configured and the synthesiser forbidden."""
    monkeypatch.setattr(
        get_settings(), "internalization_room_runner_key", RUNNER_KEY, raising=False
    )

    async def _never_voiced(text: str, **_: Any) -> None:
        raise AssertionError(f"a costura pediu um clipe ao sintetizador: {text!r}")

    monkeypatch.setattr(room, "synthesize_facilitator_speech", _never_voiced)
    return _the_app(db_session)


@pytest.fixture()
async def seam(seam_app):
    """The door where the runner's base URL points, with the key already presented."""
    async with httpx.AsyncClient(
        transport=ASGITransport(app=seam_app),
        base_url=BASE_URL,
        headers={"X-Access-Code": RUNNER_KEY},
    ) as c:
        yield c


@pytest.fixture()
def over_the_seam(seam_app, monkeypatch: pytest.MonkeyPatch):
    """`run` opening its own client, over the door this test mounted instead of the network.

    `httpx.AsyncClient` itself, because that is what the runner reaches for and there is no
    seam of its own to replace — the runner is the thing under test, network and all, and
    `monkeypatch` puts the real one back.
    """
    made = httpx.AsyncClient

    def _client(**kwargs: Any) -> httpx.AsyncClient:
        return made(**{**kwargs, "transport": ASGITransport(app=seam_app)})

    monkeypatch.setattr(httpx, "AsyncClient", _client)


def _her_script(tmp_path: Path, *, expect: dict[str, Any], rounds: int = 2) -> Path:
    """One script in her shape: her keys, her clips, her frases, her expectations."""
    second = {
        "frases": [
            {
                "clipKey": "S1",
                "coversFrom": 0,
                "coversTo": 10,
                "text": (
                    "Noemi ouviu, nos campos de Moabe, que o Senhor tinha visitado o seu povo "
                    "e dado pão a eles."
                ),
                "supersedes": 0,
            }
        ],
        "expect": {"conferida": True, "findings": []},
    }
    script = {
        "name": "P02-causa-a-mais",
        "pericopeId": "P02",
        "language": "Brazilian Portuguese",
        "why": "the bread news is present and an extra cause is added beside it",
        "draft": {
            "clips": [{"key": "S1", "durationMs": 20000}, {"key": "S2", "durationMs": 25000}]
        },
        "rounds": [
            {
                "frases": [
                    {
                        "clipKey": "S1",
                        "coversFrom": 0,
                        "coversTo": 10,
                        "text": (
                            "Noemi ouviu que o Senhor tinha dado pão ao seu povo, e decidiu "
                            "voltar para Judá porque as noras pediram."
                        ),
                    },
                    {
                        "clipKey": "S2",
                        "coversFrom": 0,
                        "coversTo": 12,
                        "text": "Ela saiu do lugar onde estava, com as duas noras, pela estrada.",
                    },
                ],
                "expect": expect,
            },
            second,
        ][:rounds],
    }
    path = tmp_path / "P02-causa-a-mais.json"
    path.write_text(json.dumps(script, ensure_ascii=False), encoding="utf-8")
    return path


def _args(script: Path, out: Path) -> argparse.Namespace:
    return argparse.Namespace(
        base_url=BASE_URL, script=str(script), out=str(out), access_code=RUNNER_KEY
    )


async def test_the_runner_plays_her_script_verbatim_and_exports_the_checks(seam, tmp_path) -> None:
    script = load_script(_her_script(tmp_path, expect={**HER_EXPECTATION, "spoken_names_frase": 9}))

    session_id = await open_session(script, seam)
    played: list[Any] = []
    await play(script, seam, session_id=session_id, played=played)
    report, transcript = export(
        script,
        session_id=session_id,
        base_url=BASE_URL,
        played=played,
        out=tmp_path / "reports",
        stamp="2026-09-11T03-00-00",
    )

    body = json.loads(report.read_text(encoding="utf-8"))
    assert (body["name"], body["pericopeId"], body["sessionId"]) == (
        "P02-causa-a-mais",
        "P02",
        session_id,
    )
    assert [one["idx"] for one in body["rounds"]] == [0, 1]
    first = body["rounds"][0]
    assert [(f["kind"], f["frase"]) for f in first["findings"]] == [("addition", 1)]
    assert first["conferida"] is False
    assert first["checks"] == ["the voice does not name frase 9"], (
        "a seção de checks é o que a Marcia lê: a falha em palavras dela, por rodada"
    )
    assert body["rounds"][1]["conferida"] is True
    assert "the voice does not name frase 9" in transcript.read_text(encoding="utf-8")
    assert report.name == "P02-causa-a-mais.2026-09-11T03-00-00.json"


async def test_a_failed_check_exits_one(over_the_seam, tmp_path) -> None:
    script = _her_script(tmp_path, expect={**HER_EXPECTATION, "spoken_names_frase": 9})

    code = await bt_golden_runner.run(_args(script, tmp_path / "reports"))

    assert code == 1, "um check reprovado é o portão: a saída tem de contar isso a um CI"
    assert list((tmp_path / "reports").glob("P02-causa-a-mais.*.json"))


async def test_a_clean_run_exits_zero(over_the_seam, tmp_path) -> None:
    script = _her_script(tmp_path, expect=HER_EXPECTATION)

    code = await bt_golden_runner.run(_args(script, tmp_path / "reports"))

    assert code == 0
    exported = list((tmp_path / "reports").glob("P02-causa-a-mais.*.json"))
    assert len(json.loads(exported[0].read_text(encoding="utf-8"))["rounds"]) == 2, (
        "sair zero não é o mesmo que ter jogado o roteiro: as duas rodadas dela têm de estar "
        "no relatório"
    )


async def test_an_http_error_exits_two_and_still_exports(over_the_seam, tmp_path) -> None:
    script = json.loads(_her_script(tmp_path, expect=HER_EXPECTATION).read_text(encoding="utf-8"))
    script["rounds"][1]["frases"][0]["coversFrom"] = 13
    script["rounds"][1]["frases"][0]["coversTo"] = 19
    path = tmp_path / "P02-causa-a-mais.json"
    path.write_text(json.dumps(script, ensure_ascii=False), encoding="utf-8")

    code = await bt_golden_runner.run(_args(path, tmp_path / "reports"))

    assert code == 2, "um erro HTTP não é um roteiro reprovado, e o runner dela os separa"
    exported = list((tmp_path / "reports").glob("P02-causa-a-mais.*.json"))
    assert exported, (
        "a rodada que já foi paga ao modelo fica na mão de quem rodou, mesmo quando a "
        "seguinte morre"
    )
    assert len(json.loads(exported[0].read_text(encoding="utf-8"))["rounds"]) == 1
