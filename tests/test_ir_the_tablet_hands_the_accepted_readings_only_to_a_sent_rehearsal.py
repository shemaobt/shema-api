from __future__ import annotations

import io
import json
import uuid
import wave
from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import internalization_room as room_service
from app.services.internalization_room.llm import CACHE_BREAK
from tests.device_harness import TABLET_TEAM, a_linked_tablet
from tests.hard_stretch_harness import MemoryStore
from tests.hearing_harness import nothing_settles, the_transcriber_hears
from tests.room_harness import the_room_speaks
from tests.turn_harness import the_room_agent_is

IR = "/api/internalization-room"
SANDAL = "Ele tirou a sandália e deu pro Boaz."
HEADER = "ACCEPTED READINGS FOR THE SCENE THIS TELLING CHECKS (a note from the app"
P11_S4_R5 = (
    "- R5: A team telling 'and gave it to Boaz' is correct, not an addition. "
    "The voice accepts it and does not correct or remark on it."
)


def recording(seconds: float, tone: int) -> bytes:
    frames = int(seconds * 16_000)
    sample = (tone % 30_000).to_bytes(2, "little", signed=True)
    out = io.BytesIO()
    with wave.open(out, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16_000)
        wav.writeframes(sample * frames)
    return out.getvalue()


class Guide:
    def __init__(self) -> None:
        self.systems: list[str] = []

    async def __call__(self, *, system_prompt: str, user_content: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        self.systems.append(system_prompt)
        return "Obrigado. Vamos ver essa cena juntos."


@dataclass
class Tablet:
    client: httpx.AsyncClient
    guide: Guide
    answers: list[str] = field(default_factory=list)


@pytest.fixture()
async def tablet(db_session: AsyncSession, rival_factory, monkeypatch: pytest.MonkeyPatch):
    from fastapi import FastAPI

    from app.api.internalization_room import router as room_router
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers
    from app.services.internalization_room import hearing
    from app.services.internalization_room.takes import take_store

    answers: list[str] = []

    async def _transcribe(audio: bytes, **_: Any) -> str:
        return answers.pop(0)

    monkeypatch.setattr(hearing, "transcribe_audio", _transcribe)
    the_room_speaks(monkeypatch)
    guide = Guide()
    the_room_agent_is(monkeypatch, turn=guide)
    nothing_settles(monkeypatch)
    bucket = MemoryStore()

    test_app = FastAPI()
    test_app.include_router(room_router, prefix=IR)
    register_exception_handlers(test_app)

    async def _get_db():
        async with rival_factory() as session:
            yield session

    test_app.dependency_overrides[get_db] = _get_db
    test_app.dependency_overrides[take_store] = lambda: bucket
    linked = await a_linked_tablet(db_session, team_id=TABLET_TEAM)
    async with httpx.AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test", headers=linked.headers
    ) as client:
        yield Tablet(client=client, guide=guide, answers=answers)


async def a_p11_session_with_a_scene_4_rehearsal(
    tablet: Tablet, db: AsyncSession
) -> tuple[str, str]:
    session = await room_service.create_session(
        db, project_id=TABLET_TEAM, language="pt", pericope="P11"
    )
    session_id = str(session.id)
    opened = await tablet.client.post(f"{IR}/sessions/{session_id}/turns")
    assert opened.status_code == 200, opened.text
    kept = await tablet.client.post(
        f"{IR}/sessions/{session_id}/scene-rehearsals",
        data={"scene": "S4"},
        files={"file": ("cena.wav", recording(40, 1), "audio/wav")},
    )
    assert kept.status_code == 200, kept.text
    rehearsal_id = str(kept.json()["rehearsal_id"])
    tablet.answers.append(SANDAL)
    frase = await tablet.client.post(
        f"{IR}/sessions/{session_id}/scene-rehearsals/{rehearsal_id}/frases",
        data={"starts_ms": "0", "ends_ms": "4000"},
        files={"file": ("frase.wav", recording(1, 100), "audio/wav")},
    )
    assert frase.status_code == 200, frase.text
    tablet.guide.systems.clear()
    return session_id, rehearsal_id


async def test_terminei_on_a_p11_scene_4_rehearsal_hands_the_guide_her_header_and_r5_last(
    tablet: Tablet, db_session: AsyncSession
) -> None:
    session_id, rehearsal_id = await a_p11_session_with_a_scene_4_rehearsal(tablet, db_session)

    sent = await tablet.client.post(
        f"{IR}/sessions/{session_id}/scene-rehearsals/{rehearsal_id}/send",
        data={"turn_id": str(uuid.uuid4())},
    )

    assert sent.status_code == 200, sent.text
    facts = tablet.guide.systems[-1].partition(CACHE_BREAK)[2]
    assert facts.split("\n\n")[-1].startswith(HEADER)
    assert facts.endswith(f"\n{P11_S4_R5}"), "o «terminei» do tablet chegava ao Guia sem o R5"


async def test_the_same_telling_spoken_on_the_ordinary_microphone_hands_the_guide_no_accepted_readings(  # noqa: E501
    tablet: Tablet, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_id, _ = await a_p11_session_with_a_scene_4_rehearsal(tablet, db_session)
    the_transcriber_hears(monkeypatch, SANDAL, "pt", 1.0)

    spoken = await tablet.client.post(
        f"{IR}/sessions/{session_id}/turns",
        files={"file": ("fala.wav", recording(2, 7), "audio/wav")},
    )

    assert spoken.status_code == 200, spoken.text
    assert tablet.guide.systems, "o Guia nem foi chamado"
    assert not any("ACCEPTED READINGS" in system for system in tablet.guide.systems), (
        "a mesma história falada no microfone comum levava as leituras aceitas"
    )
