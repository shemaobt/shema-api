"""The golden runner drives a session through the text seam and exports the judge's input.

One script, one base URL. What comes out is the transcript block her runner pastes into the
judge prompt — turn index, team turn, guide turn, outcome tag — so a run against this room
and a run against hers are read by the same judge from the same shape.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import golden_doors, router
from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import register_exception_handlers
from scripts.golden_runner import (
    Played,
    export,
    exported,
    judge_transcript,
    load_script,
    open_session,
    play,
)
from tests.text_seam_harness import (
    BEARER,
    GUIDE_LINE,
    RUNNER_KEY,
    TEAM_LINE,
    the_models_answer,
)

MOTHER_TONGUE_NOTE = (
    "[A equipe falou na língua materna por cerca de 40 segundos; sem transcrição — nenhuma "
    "palavra chegou até você.]"
)


@pytest.fixture()
async def seam(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    from fastapi import FastAPI

    monkeypatch.setattr(
        get_settings(), "internalization_room_runner_key", RUNNER_KEY, raising=False
    )
    the_models_answer(monkeypatch)

    async def _settled(**_: Any) -> None:
        return None

    monkeypatch.setattr(golden_doors, "settle_coverage", _settled)
    test_app = FastAPI()
    test_app.include_router(router, prefix="/api/internalization-room")
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    async with httpx.AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://test/api/internalization-room/",
        headers=BEARER,
    ) as c:
        yield c


REHEARSAL_TEXT = (
    "[A equipe ensaiou esta cena na língua materna e traduziu o ensaio da cena frase por frase "
    "(2 frases). Segue a tradução, na ordem:] Noemi disse: voltem. Rute ficou com ela."
)
EARLIER_FACT = (
    "EARLIER PASSAGES FOR THIS TEAM: Approved: Ruth 1:1\u20135. Not worked yet: Ruth 1:6\u201314."
)


def _her_rehearsing_script(tmp_path: Path) -> Path:
    path = tmp_path / "P03-a-scene-rehearsed.json"
    path.write_text(
        json.dumps(
            {
                "name": "P03-a-scene-rehearsed",
                "pericopeId": "P03",
                "language": "Brazilian Portuguese",
                "why": "the earlier passages, a scene rehearsal and a word after it",
                "earlierPassages": {"P01": "approved", "P02": "not_worked"},
                "turns": [
                    {"kickoff": True},
                    {
                        "rehearsal": {
                            "pieces": ["Noemi disse: voltem.", " Rute ficou com ela. "],
                            "sceneId": "S1",
                        },
                        "sceneRehearsals": ["S1"],
                    },
                    {"team": TEAM_LINE},
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def _her_script(tmp_path: Path) -> Path:
    path = tmp_path / "P01-three-turns.json"
    path.write_text(
        json.dumps(
            {
                "name": "P01-three-turns",
                "pericopeId": "P01",
                "language": "Brazilian Portuguese",
                "why": "three turns, one of each note",
                "turns": [
                    {"kickoff": True, "expect": {"no_fail_safe": True}},
                    {"team": TEAM_LINE},
                    {"motherTongue": 40, "expect": {"no_fail_safe": True}},
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


async def test_the_export_is_the_transcript_block_her_judge_is_handed(
    seam, tmp_path, monkeypatch
) -> None:
    agent = the_models_answer(monkeypatch)
    script = load_script(_her_script(tmp_path))

    session_id = await open_session(script, seam)
    played: list[Played] = []
    await play(script, seam, session_id=session_id, played=played)
    opening = agent.guide_inputs[0]
    report, transcript = export(
        script,
        session_id=session_id,
        base_url=str(seam.base_url),
        played=played,
        out=tmp_path / "reports",
        stamp="2026-09-11T03-00-00",
    )

    assert transcript.read_text(encoding="utf-8") == (
        f"[turn 0]\nTEAM: {opening}\nGUIDE (pass): {GUIDE_LINE}\n\n"
        f"[turn 1]\nTEAM: {TEAM_LINE}\nGUIDE (pass): {GUIDE_LINE}\n\n"
        f"[turn 2]\nTEAM: {MOTHER_TONGUE_NOTE}\nGUIDE (pass): {GUIDE_LINE}\n"
    ), "o bloco tem de entrar no prompt do juiz sem edição, no formato do runner dela"
    turns = json.loads(report.read_text(encoding="utf-8"))["turns"]
    assert [(t["idx"], t["team"], t["guide"], t["outcome"]) for t in turns] == [
        (0, opening, GUIDE_LINE, "pass"),
        (1, TEAM_LINE, GUIDE_LINE, "pass"),
        (2, MOTHER_TONGUE_NOTE, GUIDE_LINE, "pass"),
    ]
    assert report.name == "P01-three-turns.2026-09-11T03-00-00.json"


async def test_a_turn_that_fails_leaves_the_turns_already_played_in_hand(
    seam, tmp_path, monkeypatch
) -> None:
    from app.services import internalization_room as room

    real_turn = room.run_comprehension_turn
    answered = 0

    async def _dies_on_the_second(db: Any, session: Any, **kwargs: Any) -> Any:
        nonlocal answered
        answered += 1
        if answered == 2:
            raise RuntimeError("a API caiu no meio da sessão")
        return await real_turn(db, session, **kwargs)

    monkeypatch.setattr(room, "run_comprehension_turn", _dies_on_the_second)
    seam._transport.raise_app_exceptions = False
    script = load_script(_her_script(tmp_path))
    played: list[Played] = []

    with pytest.raises(httpx.HTTPStatusError):
        await play(script, seam, session_id=await open_session(script, seam), played=played)

    assert [(t.idx, t.guide, t.outcome) for t in played] == [(0, GUIDE_LINE, "pass")], (
        "um 500 no último turno jogava fora todos os turnos já pagos, sem nem o id da sessão"
    )


async def test_the_runner_sends_her_earlier_passages_her_rehearsal_and_the_scenes_rehearsed(
    seam, tmp_path, monkeypatch
) -> None:
    the_models_answer(monkeypatch)
    sent: list[tuple[str, dict[str, Any]]] = []

    async def _seen(request: httpx.Request) -> None:
        sent.append((request.url.path.rsplit("/", 1)[-1], json.loads(request.content)))

    seam.event_hooks["request"].append(_seen)
    script = load_script(_her_rehearsing_script(tmp_path))

    session_id = await open_session(script, seam)
    played: list[Played] = []
    await play(script, seam, session_id=session_id, played=played)

    assert sent[0] == (
        "session",
        {
            "pericopeId": "P03",
            "language": "Brazilian Portuguese",
            "earlierPassages": {"P01": "approved", "P02": "not_worked"},
        },
    ), "a sessão abria sem o estado das passagens anteriores que o roteiro dela fixa"
    assert [body.get("sceneRehearsals") for _door, body in sent[1:]] == [None, ["S1"], ["S1"]], (
        "a lista de cenas ensaiadas segue de um turno para o outro, como no driver dela"
    )
    assert played[1].team == REHEARSAL_TEXT, "o turno de ensaio chegava ao Guia como texto vazio"


async def test_the_judge_reads_what_the_app_told_the_guide_as_her_app_status_lines(
    seam, tmp_path, monkeypatch
) -> None:
    agent = the_models_answer(monkeypatch)
    script = load_script(_her_rehearsing_script(tmp_path))
    session_id = await open_session(script, seam)
    played: list[Played] = []
    await play(script, seam, session_id=session_id, played=played)

    status = "APP STATUS (what the app told the guide this turn): "
    scenes = (
        "SCENE REHEARSALS: parts whose recorded and translated scene rehearsal has reached you: "
        "S1. Parts with none: S2, S3."
    )
    assert judge_transcript(played) == (
        f"[turn 0]\n{status}{EARLIER_FACT}\nTEAM: {agent.guide_inputs[0]}\n"
        f"GUIDE (pass): {GUIDE_LINE}\n\n"
        f"[turn 1]\n{status}{scenes}\n{status}{EARLIER_FACT}\nTEAM: {REHEARSAL_TEXT}\n"
        f"GUIDE (pass): {GUIDE_LINE}\n\n"
        f"[turn 2]\n{status}{scenes}\n{status}{EARLIER_FACT}\nTEAM: {TEAM_LINE}\n"
        f"GUIDE (pass): {GUIDE_LINE}"
    ), "o juiz não via o que o app disse ao Guia, então worked_passage_assumed nunca era julgado"


async def test_a_run_judged_again_from_its_export_reads_the_same_app_status_lines(
    seam, tmp_path, monkeypatch
) -> None:
    the_models_answer(monkeypatch)
    script = load_script(_her_rehearsing_script(tmp_path))
    session_id = await open_session(script, seam)
    played: list[Played] = []
    await play(script, seam, session_id=session_id, played=played)
    report, _transcript = export(
        script,
        session_id=session_id,
        base_url=str(seam.base_url),
        played=played,
        out=tmp_path / "reports",
        stamp="2026-10-05T03-00-00",
    )

    _script, result, _base = exported(report)

    assert judge_transcript(result.played) == judge_transcript(played), (
        "rejulgar um relatório apagava as linhas APP STATUS que o juiz leu na primeira vez"
    )
