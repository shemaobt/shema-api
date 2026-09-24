from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import text_seam
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.sessions import append_exchange, create_session
from app.services.platform.tts import SynthesizedSpeech
from tests.baker import make_app, make_role
from tests.release_harness import (
    APP_KEY,
    KEY,
    PREFIX,
    a_claimed_device,
    at_the_desk,
    desk_release,
    ready_session,
)
from tests.room_harness import room_client
from tests.text_seam_harness import GUIDE_LINE, RUNNER_KEY, TEAM_LINE, the_models_answer

LEGACY_COMPREHENSION = {
    "ledger": [
        {
            "kind": "evidence",
            "id": "ev-0",
            "unit_id": "proposition:P03:P1",
            "probe_id": "probe-0",
            "method": "micro_tellback",
            "result": "carry_to_refine",
        }
    ],
    "active_probe": {
        "id": "probe-1",
        "checkpoint_ids": ["proposition:P03:P1"],
        "method": "micro_tellback",
        "purpose": "initial_check",
        "practice_scene_ids": [],
    },
    "practiced_scene_ids": ["S1"],
    "invited_scene_id": "S2",
}


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    async with room_client(db_session, monkeypatch) as room:
        yield room


@pytest.fixture()
async def turns(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    from app.api.internalization_room import sessions as sessions_api

    async def _heard(audio: bytes, **_: Any) -> HeardSpeech:
        return HeardSpeech(text=TEAM_LINE)

    async def _voice(text: str, **_: Any) -> tuple[SynthesizedSpeech, bool]:
        entry = SynthesizedSpeech(
            audio=b"audio", mime_type="audio/mpeg", etag="e", cached=False, key="tts/v/m/f/1.mp3"
        )
        return entry, False

    async def _settled_later(**_: Any) -> None:
        return None

    the_models_answer(monkeypatch)
    monkeypatch.setattr(sessions_api, "heard_speech", _heard)
    monkeypatch.setattr(sessions_api.room, "synthesize_facilitator_speech", _voice)
    monkeypatch.setattr(sessions_api, "settle_coverage", _settled_later)
    monkeypatch.setattr(text_seam, "settle_coverage", _settled_later)
    async with room_client(db_session, monkeypatch, runner_key=RUNNER_KEY) as room:
        yield room


async def _an_august_session(db: AsyncSession):
    session = await create_session(db, language="pt", pericope="P03")
    session = await append_exchange(db, session, team_utterance="", guide_response=GUIDE_LINE)
    session.comprehension = LEGACY_COMPREHENSION
    await db.commit()
    return session


@pytest.fixture()
async def room_app(db_session: AsyncSession):
    app = await make_app(db_session, app_key=APP_KEY, name="Internalization Room")
    await make_role(db_session, app.id, role_key="facilitator", label="Facilitator", is_system=True)
    return app


async def test_the_desks_packet_says_v0_7_and_carries_no_comprehension_or_readiness(
    client, db_session: AsyncSession, room_app
) -> None:
    project, _credential = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=project.id)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)

    read = await client.get(desk_release(session.id), headers=desk)

    assert read.status_code == 200, read.text
    packet = read.json()
    assert packet["schema_version"] == "tripod.internalization-release.v0.7"
    assert "comprehension" not in packet, (
        "o pacote levava ao Refine um registro de compreensão que ninguém mais escreve"
    )
    assert "readiness" not in packet, (
        "o pacote dizia ready_for_refine ao lado de um needs_more_work que nada mais resolve"
    )


async def test_a_session_holding_an_august_ledger_releases_without_counting_its_open_point(
    client, db_session: AsyncSession, room_app
) -> None:
    project, _credential = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=project.id)
    session.comprehension = LEGACY_COMPREHENSION
    await db_session.commit()
    desk, _facilitator = await at_the_desk(db_session, room_app, project)

    read = await client.get(desk_release(session.id), headers=desk)

    assert read.status_code == 200, read.text
    packet = read.json()
    assert "comprehension" not in packet
    assert packet["open_questions"] == 0, (
        "o ponto levado ao Refine no ledger de agosto contava como pergunta aberta"
    )


async def test_a_voiced_turn_on_an_august_session_leaves_its_comprehension_as_stored(
    turns, db_session: AsyncSession
) -> None:
    session = await _an_august_session(db_session)

    answered = await turns.post(
        f"{PREFIX}/sessions/{session.id}/turns",
        headers={"X-Room-Key": KEY},
        files={"file": ("answer.m4a", b"audio", "audio/m4a")},
    )
    await db_session.refresh(session)

    assert answered.status_code == 200, answered.text
    assert session.comprehension == LEGACY_COMPREHENSION, (
        "o turno falado regravava a coluna de agosto e apagava a sonda que ela guardava"
    )
    assert session.messages[-2]["text"] == TEAM_LINE


async def test_a_text_seam_turn_on_an_august_session_leaves_its_comprehension_as_stored(
    turns, db_session: AsyncSession
) -> None:
    session = await _an_august_session(db_session)

    answered = await turns.post(
        f"{PREFIX}/text-seam/turn", json={"sessionId": session.id, "text": TEAM_LINE}
    )
    await db_session.refresh(session)

    assert answered.status_code == 200, answered.text
    assert session.comprehension == LEGACY_COMPREHENSION, (
        "o turno do text seam regravava a coluna de agosto e apagava a sonda que ela guardava"
    )
    assert answered.json()["guideText"] == GUIDE_LINE
