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

from app.api.internalization_room import router, text_seam
from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import register_exception_handlers
from scripts.golden_runner import Played, export, load_script, open_session, play
from tests.test_ir_the_text_seam_enters_the_real_turn import (
    GUIDE_LINE,
    RUNNER_KEY,
    TEAM_LINE,
    _the_models_answer,
)

OPENING_NOTE = (
    "[A sessão acabou de começar. A equipe abriu a passagem P01 e está à mesa, pronta para "
    "começar. Fale primeiro.]"
)
MOTHER_TONGUE_NOTE = (
    "[A equipe falou na língua materna por cerca de 40 segundos; sem transcrição — nenhuma "
    "palavra chegou até você.]"
)
OFF_BRIDGE_LINE = (
    "Que bom — vocês experimentaram na língua de vocês. Eu não consigo conferir essas "
    "palavras diretamente. Agora, alguém pode me contar em português o que vocês disseram?"
)


@pytest.fixture()
async def seam(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    from fastapi import FastAPI

    monkeypatch.setattr(
        get_settings(), "internalization_room_runner_key", RUNNER_KEY, raising=False
    )
    _the_models_answer(monkeypatch)

    async def _settled(**_: Any) -> None:
        return None

    monkeypatch.setattr(text_seam, "settle_coverage", _settled)
    test_app = FastAPI()
    test_app.include_router(router, prefix="/api/internalization-room")
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    async with httpx.AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://test/api/internalization-room/text-seam/",
        headers={"X-Access-Code": RUNNER_KEY},
    ) as c:
        yield c


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


async def test_the_export_is_the_transcript_block_her_judge_is_handed(seam, tmp_path) -> None:
    script = load_script(_her_script(tmp_path))

    session_id = await open_session(script, seam)
    played: list[Played] = []
    await play(script, seam, session_id=session_id, played=played)
    report, transcript = export(
        script,
        session_id=session_id,
        base_url=str(seam.base_url),
        played=played,
        out=tmp_path / "reports",
        stamp="2026-09-11T03-00-00",
    )

    assert transcript.read_text(encoding="utf-8") == (
        f"[turn 0]\nTEAM: {OPENING_NOTE}\nGUIDE (pass): {GUIDE_LINE}\n\n"
        f"[turn 1]\nTEAM: {TEAM_LINE}\nGUIDE (pass): {GUIDE_LINE}\n\n"
        f"[turn 2]\nTEAM: {MOTHER_TONGUE_NOTE}\nGUIDE (fail_safe): {OFF_BRIDGE_LINE}\n"
    ), "o bloco tem de entrar no prompt do juiz sem edição, no formato do runner dela"
    turns = json.loads(report.read_text(encoding="utf-8"))["turns"]
    assert [(t["idx"], t["team"], t["guide"], t["outcome"]) for t in turns] == [
        (0, OPENING_NOTE, GUIDE_LINE, "pass"),
        (1, TEAM_LINE, GUIDE_LINE, "pass"),
        (2, MOTHER_TONGUE_NOTE, OFF_BRIDGE_LINE, "fail_safe"),
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
