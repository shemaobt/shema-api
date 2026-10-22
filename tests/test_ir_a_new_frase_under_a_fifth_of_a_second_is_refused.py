from __future__ import annotations

from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PauseCannotMove
from app.db.models.internalization_room import IRSegment
from app.services.internalization_room.segments import capture_segment, final_segments
from tests.device_harness import TABLET_TEAM, a_linked_tablet
from tests.hard_stretch_harness import (
    DEVICE,
    IR,
    MemoryStore,
    a_session,
    current,
    rehearse,
    retro_takes,
)
from tests.room_harness import nothing_is_read_ahead, rehearsed_in_parts_of

AUDIO = b"a equipe contou um trecho curto demais"


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    from fastapi import FastAPI

    from app.api.internalization_room import back_translation as bt_api
    from app.api.internalization_room import router as room_router
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers
    from app.services.internalization_room import takes as takes_service

    asked: list[bytes] = []

    async def _transcribe(audio: bytes, **_: Any) -> str:
        asked.append(audio)
        return "algo que a equipe contou"

    monkeypatch.setattr(bt_api, "heard", _transcribe)
    nothing_is_read_ahead(monkeypatch)
    bucket = MemoryStore()
    monkeypatch.setattr(takes_service, "_store", lambda *_, **__: bucket)

    test_app = FastAPI()
    test_app.include_router(room_router, prefix=IR)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    tablet = await a_linked_tablet(db_session, team_id=TABLET_TEAM)
    async with httpx.AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test", headers=tablet.headers
    ) as c:
        c.asked = asked  # type: ignore[attr-defined]
        yield c


async def _chunk(
    client: httpx.AsyncClient, session_id: str, take_id: str, starts_ms: int, ends_ms: int
) -> httpx.Response:
    return await client.post(
        f"{IR}/sessions/{session_id}/back-translation/chunks",
        headers={"X-Room-Device": DEVICE},
        data={"take_id": take_id, "starts_ms": str(starts_ms), "ends_ms": str(ends_ms)},
        files={"file": ("trecho.m4a", AUDIO, "audio/mp4")},
    )


async def test_a_new_frase_of_a_tenth_of_a_second_is_refused_before_anything_is_kept(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    take_id = await rehearse(client, session_id)
    kept = len(await retro_takes(db_session, session_id))

    refused = await _chunk(client, session_id, take_id, 0, 100)

    assert refused.status_code == 400, refused.text
    assert refused.json()["code"] == "PAUSE_CANNOT_STAND_THERE"
    assert client.asked == [], (  # type: ignore[attr-defined]
        "uma frase de 100 ms era mandada ao transcritor antes de alguém olhar o tamanho dela"
    )
    assert len(await retro_takes(db_session, session_id)) == kept, (
        "a gravação da frase recusada ficava guardada como mais uma contagem"
    )
    assert await current(db_session, session_id) == [], (
        "uma frase de 100 ms ficava de pé, com número e veredito"
    )


async def test_a_new_frase_of_exactly_a_fifth_of_a_second_is_kept(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    take_id = await rehearse(client, session_id)

    kept = await _chunk(client, session_id, take_id, 0, 200)

    assert kept.status_code == 200, kept.text
    assert [(one.starts_ms, one.ends_ms) for one in await current(db_session, session_id)] == [
        (0, 200)
    ], "uma frase de 200 ms, o mínimo dela, era recusada"


async def test_a_short_frase_stored_before_the_floor_can_still_be_told_again_on_its_slice(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    take_id = await rehearse(client, session_id)
    db_session.add(
        IRSegment(
            id="a-sliver-from-before-the-floor",
            session_id=session_id,
            project_id=TABLET_TEAM,
            parent_id=None,
            ordinal=1,
            take_id=take_id,
            starts_ms=0,
            ends_ms=100,
            pass_number=1,
            tellings=1,
            transcript="uma frase que coube antes do piso",
        )
    )
    await db_session.commit()

    told_again = await _chunk(client, session_id, take_id, 0, 100)

    assert told_again.status_code == 200, told_again.text
    assert [
        (one.starts_ms, one.ends_ms, one.tellings) for one in await current(db_session, session_id)
    ] == [(0, 100, 2)], "recontar a frase curta de antes do piso virava recusa de frase nova"


async def test_a_new_frase_under_a_fifth_of_a_second_is_refused_at_the_capture_whatever_the_door(
    db_session: AsyncSession,
) -> None:
    session, parts = await rehearsed_in_parts_of(db_session, [3, 3])

    with pytest.raises(PauseCannotMove) as refused:
        await capture_segment(
            db_session,
            session,
            take_id=parts[0].id,
            starts_ms=3000,
            ends_ms=3100,
            transcript="uma frase curta demais",
        )

    assert refused.value.code == "PAUSE_CANNOT_STAND_THERE"
    assert len(await final_segments(db_session, session.id)) == 6, (
        "uma frase de 100 ms era guardada como frase de pé"
    )
