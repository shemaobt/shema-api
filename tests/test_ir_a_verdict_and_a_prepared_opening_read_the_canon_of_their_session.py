from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession
from app.services import internalization_room as room
from app.services.internalization_room import prepare_opening as preparing
from app.services.internalization_room.sessions import create_session
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
from tests.text_seam_harness import RUNNER_KEY, ScriptedAgent
from tests.turn_harness import the_room_agent_is

NEW_PIN = "a" * 40
SEAM = "/api/internalization-room/text-seam/back-translation"
THE_LAST_SCENE = "### Scene 3 —"
THE_PROPOSITIONS = "## 4. Level 3"
INTO_THE_LAST_SCENE_PT = "Vamos pra Internalização da última cena."
INTO_THE_LAST_SCENE_EN = "Let's go to the Internalization of the last scene."
VENDORED_FIRST_SCENE = "Famine and exile to Moab"
KEPT_FIRST_SCENE = "The kept first scene of the book"
PREPARED = "Vamos começar pela Familiarização. Primeiro eu conto a passagem inteira."
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


def _the_kept_p01_names_its_first_scene_its_own_way(tree: Path) -> None:
    (page,) = (tree / "vendor" / "meaning-map").glob("P01-*.md")
    told = page.read_text(encoding="utf-8")
    page.write_text(told.replace(VENDORED_FIRST_SCENE, KEPT_FIRST_SCENE), encoding="utf-8")


class Speaker:
    def __init__(self, said: str) -> None:
        self.said = said

    async def __call__(self, *, system_prompt: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return self.said


async def _a_panorama_with_a_line_ready_for_p01(db: AsyncSession) -> IRSession:
    panorama = await create_session(db, pericope="OV-Ruth", language="pt")
    panorama.prepared_speech = PREPARED
    panorama.prepared_audio_key = "tts/prepared.mp3"
    panorama.prepared_pericope = "P01"
    await db.commit()
    return panorama


async def _prepared_speech_of(db: AsyncSession, session_id: str) -> str | None:
    return await db.scalar(select(IRSession.prepared_speech).where(IRSession.id == session_id))


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


async def test_the_opening_prepared_on_a_panorama_open_when_a_new_canon_is_published_is_written_from_its_own_map(  # noqa: E501
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    voice = ScriptedAgent([])
    the_room_agent_is(monkeypatch, turn=voice)

    async def _voiced(*_: object, **__: object) -> tuple[SimpleNamespace, None]:
        return SimpleNamespace(key="tts/prepared.mp3"), None

    monkeypatch.setattr(preparing, "synthesize_facilitator_speech", _voiced)
    panorama = await create_session(db_session, pericope="OV-Ruth", language="pt")
    await db_session.commit()
    the_canon_moves_on(
        monkeypatch, tmp_path, NEW_PIN, keeping=_the_kept_p01_names_its_first_scene_its_own_way
    )

    await preparing.prepare_opening(panorama.id, pericope="P01")

    (written_from,) = voice.guide_systems
    assert KEPT_FIRST_SCENE in written_from, (
        "a abertura preparada no panorama foi escrita do mapa novo, não do mapa da sessão"
    )
    assert VENDORED_FIRST_SCENE not in written_from


async def test_a_line_prepared_on_a_panorama_of_another_canon_is_not_handed_to_the_passage(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    panorama = await _a_panorama_with_a_line_ready_for_p01(db_session)
    the_canon_moves_on(monkeypatch, tmp_path, NEW_PIN)
    passage = await create_session(db_session, pericope="P01", language="pt")
    await db_session.commit()

    assert await preparing.hand_over(db_session, panorama, passage) is False, (
        "a linha escrita no mapa antigo foi entregue a uma sessão aberta no mapa novo"
    )
    assert await _prepared_speech_of(db_session, passage.id) is None
    assert await _prepared_speech_of(db_session, panorama.id) == PREPARED


async def test_a_line_prepared_on_a_panorama_of_a_kept_canon_is_handed_to_a_passage_of_that_canon(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    panorama = await _a_panorama_with_a_line_ready_for_p01(db_session)
    passage = await create_session(db_session, pericope="P01", language="pt")
    await db_session.commit()
    the_canon_moves_on(monkeypatch, tmp_path, NEW_PIN)

    assert await preparing.hand_over(db_session, panorama, passage) is True, (
        "a linha do mapa antigo deixou de chegar a uma sessão aberta no mesmo mapa"
    )
    assert await _prepared_speech_of(db_session, passage.id) == PREPARED
    assert await _prepared_speech_of(db_session, panorama.id) is None
