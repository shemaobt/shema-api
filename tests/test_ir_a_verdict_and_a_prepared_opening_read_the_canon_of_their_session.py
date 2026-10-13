from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession
from app.services import internalization_room as room
from tests.canon_harness import the_canon_moves_on
from tests.release_harness import a_claimed_device, team_headers
from tests.room_harness import (
    P,
    heard_every_part,
    nothing_is_read_ahead,
    press_terminei,
    rehearsed_in_parts,
    room_client,
    the_analyst_reads,
    the_room_speaks,
)
from tests.text_seam_harness import RUNNER_KEY
from tests.turn_harness import the_room_agent_is

NEW_PIN = "a" * 40
SEAM = "/api/internalization-room/text-seam/back-translation"
THE_LAST_SCENE = "### Scene 3 —"
THE_PROPOSITIONS = "## 4. Level 3"
INTO_THE_LAST_SCENE_PT = "Vamos pra Internalização da última cena."
INTO_THE_LAST_SCENE_EN = "Let's go to the Internalization of the last scene."
INTO_THE_LAST_SCENE = {
    "before": {"at": "familiarization"},
    "after": {"at": "internalization", "part": 2},
    "by": ["entrance"],
}


def _the_kept_map_has_no_last_scene(pericope: str) -> Callable[[Path], None]:
    def keeping(tree: Path) -> None:
        (page,) = (tree / "vendor" / "meaning-map").glob(f"{pericope}-*.md")
        told = page.read_text(encoding="utf-8")
        last = told.index(THE_LAST_SCENE)
        page.write_text(told[:last] + told[told.index(THE_PROPOSITIONS) :], encoding="utf-8")

    return keeping


class Speaker:
    def __init__(self, said: str) -> None:
        self.said = said

    async def __call__(self, *, system_prompt: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return self.said


async def _the_last_step_of(db: AsyncSession, session_id: str) -> dict[str, Any]:
    messages = await db.scalar(select(IRSession.messages).where(IRSession.id == session_id))
    assert messages
    return dict(messages[-1]["moment"])


async def test_a_verdict_pressed_on_the_tablet_moves_the_moment_by_the_scenes_of_its_kept_map(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    the_analyst_reads(monkeypatch)
    the_room_speaks(monkeypatch)
    the_room_agent_is(monkeypatch, turn=Speaker(INTO_THE_LAST_SCENE_PT))
    project, credential = await a_claimed_device(db_session)
    session, _parts = await rehearsed_in_parts(db_session, 2, project_id=project.id)
    the_canon_moves_on(monkeypatch, tmp_path, NEW_PIN, keeping=_the_kept_map_has_no_last_scene(P))

    async with room_client(db_session, monkeypatch) as client:
        client.headers.update(team_headers(credential))
        pressed = await press_terminei(
            client, session.id, report=await heard_every_part(db_session, session.id)
        )

    assert pressed.status_code == 200, pressed.text
    assert await _the_last_step_of(db_session, session.id) == INTO_THE_LAST_SCENE, (
        "o veredito contou as cenas do mapa novo, e a última cena da sessão era outra"
    )


async def test_a_verdict_played_through_the_text_seam_moves_the_moment_by_the_scenes_of_its_kept_map(  # noqa: E501
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    the_analyst_reads(monkeypatch)
    the_room_agent_is(monkeypatch, turn=Speaker(INTO_THE_LAST_SCENE_EN))
    nothing_is_read_ahead(monkeypatch)

    async def _never_voiced(text: str, **_: Any) -> None:
        raise AssertionError(f"a costura pediu um clipe ao sintetizador: {text!r}")

    monkeypatch.setattr(room, "synthesize_facilitator_speech", _never_voiced)
    async with room_client(db_session, monkeypatch, runner_key=RUNNER_KEY) as seam:
        declared = await seam.post(
            f"{SEAM}/session",
            json={
                "pericopeId": "P02",
                "language": "English",
                "clips": [{"key": "S1", "durationMs": 20000}],
            },
        )
        assert declared.status_code == 200, declared.text
        session_id = str(declared.json()["sessionId"])
        the_canon_moves_on(
            monkeypatch, tmp_path, NEW_PIN, keeping=_the_kept_map_has_no_last_scene("P02")
        )
        played = await seam.post(
            f"{SEAM}/round",
            json={
                "sessionId": session_id,
                "frases": [
                    {
                        "clipKey": "S1",
                        "coversFrom": 0,
                        "coversTo": 10,
                        "text": "Noemi ouviu que o Senhor tinha dado pão ao seu povo e voltou.",
                    }
                ],
            },
        )

    assert played.status_code == 200, played.text
    assert await _the_last_step_of(db_session, session_id) == INTO_THE_LAST_SCENE, (
        "a rodada da costura contou as cenas do mapa novo, e a última cena da sessão era outra"
    )
