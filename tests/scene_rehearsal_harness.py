"""The room a scene rehearsal case stands in: two linked tablets of one team, the Desk, the
bucket and the recognizer in memory, and the doors the team presses on the way.

Fixtures are not exported: each module keeps the three-line fixture that calls `a_room`.
"""

from __future__ import annotations

import io
import uuid
import wave
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ProjectRole
from app.db.models.auth import Role
from tests.baker import make_app, make_project_user_access, make_role, make_user, make_user_app_role
from tests.device_harness import TABLET_TEAM, a_linked_tablet
from tests.hard_stretch_harness import MemoryStore

IR = "/api/internalization-room"
P = "P01"
SAID = "a frase traduzida pela equipe"


def recording(seconds: float, tone: int) -> bytes:
    """A 16 kHz mono WAV whose bytes differ by `tone`, so two recordings never share a hash."""
    frames = int(seconds * 16_000)
    sample = (tone % 30_000).to_bytes(2, "little", signed=True)
    out = io.BytesIO()
    with wave.open(out, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16_000)
        wav.writeframes(sample * frames)
    return out.getvalue()


SCENE = recording(40, 1)


@dataclass
class Room:
    client: httpx.AsyncClient
    credential: str
    tablet_b: dict[str, str]
    desk: dict[str, str]
    bucket: MemoryStore
    heard: list[dict[str, Any]]
    signed: list[str]
    answers: list[str] = field(default_factory=list)
    while_hearing: list[Callable[[], Awaitable[Any]]] = field(default_factory=list)


@asynccontextmanager
async def a_room(
    db_session: AsyncSession, rival_factory, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[Room]:
    from fastapi import FastAPI

    from app.api.internalization_room import router as room_router
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers
    from app.services.internalization_room import hearing
    from app.services.internalization_room import takes as takes_service
    from app.services.internalization_room.takes import take_store

    heard: list[dict[str, Any]] = []
    signed: list[str] = []
    answers: list[str] = []
    while_hearing: list[Callable[[], Awaitable[Any]]] = []

    async def _transcribe(audio: bytes, **kwargs: Any) -> str:
        heard.append({"audio": audio, **kwargs})
        if while_hearing:
            await while_hearing.pop(0)()
        return answers.pop(0) if answers else SAID

    async def _sign(_bucket: str, key: str, **_: Any) -> str:
        signed.append(key)
        return f"https://storage.example/{key}"

    monkeypatch.setattr(hearing, "transcribe_audio", _transcribe)
    monkeypatch.setattr(get_settings(), "gcs_platform_bucket", "balde-de-teste", raising=False)
    monkeypatch.setattr(takes_service, "generate_signed_download_url", _sign)
    bucket = MemoryStore()

    test_app = FastAPI()
    test_app.include_router(room_router, prefix=IR)
    register_exception_handlers(test_app)

    async def _get_db():
        async with rival_factory() as session:
            yield session

    test_app.dependency_overrides[get_db] = _get_db
    test_app.dependency_overrides[take_store] = lambda: bucket

    tablet_a = await a_linked_tablet(db_session, team_id=TABLET_TEAM)
    facilitator = await make_user(db_session, email=f"leitor-{uuid.uuid4().hex[:8]}@example.com")
    await make_project_user_access(
        db_session, TABLET_TEAM, facilitator.id, role=ProjectRole.FACILITATOR
    )
    app = await make_app(db_session, app_key="internalization-room", name="Internalization Room")
    await make_role(db_session, app.id, role_key="facilitator", label="Facilitator", is_system=True)
    role = (
        await db_session.execute(
            select(Role).where(Role.app_id == app.id, Role.role_key == "facilitator")
        )
    ).scalar_one()
    await make_user_app_role(db_session, facilitator.id, app.id, role.id)
    tablet_b = await a_linked_tablet(db_session, team_id=TABLET_TEAM, facilitator=facilitator)

    from app.services.auth.issue_tokens import issue_tokens

    access, _refresh = await issue_tokens(db_session, facilitator)

    async with httpx.AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test", headers=tablet_a.headers
    ) as client:
        yield Room(
            client=client,
            credential=tablet_a.credential,
            tablet_b=tablet_b.headers,
            desk={"Authorization": f"Bearer {access}"},
            bucket=bucket,
            heard=heard,
            signed=signed,
            answers=answers,
            while_hearing=while_hearing,
        )


async def record(
    room: Room, session_id: str, audio: bytes = SCENE, scene: str | None = "S2"
) -> httpx.Response:
    return await room.client.post(
        f"{IR}/sessions/{session_id}/scene-rehearsals",
        data={} if scene is None else {"scene": scene},
        files={"file": ("cena.wav", audio, "audio/wav")},
    )


async def recorded(room: Room, session_id: str, audio: bytes = SCENE) -> str:
    kept = await record(room, session_id, audio)
    assert kept.status_code == 200, kept.text
    return str(kept.json()["rehearsal_id"])


async def translate(
    room: Room,
    session_id: str,
    rehearsal_id: str,
    place: tuple[int | None, int | None],
    audio: bytes,
    *,
    replaces: str | None = None,
) -> httpx.Response:
    starts, ends = place
    data = {
        name: str(value)
        for name, value in (("starts_ms", starts), ("ends_ms", ends), ("replaces", replaces))
        if value is not None
    }
    return await room.client.post(
        f"{IR}/sessions/{session_id}/scene-rehearsals/{rehearsal_id}/frases",
        data=data,
        files={"file": ("frase.wav", audio, "audio/wav")},
    )


async def translated(
    room: Room,
    session_id: str,
    rehearsal_id: str,
    places: list[tuple[int, int]],
    *,
    tone: int = 100,
) -> list[str]:
    for offset, place in enumerate(places):
        kept = await translate(room, session_id, rehearsal_id, place, recording(1, tone + offset))
        assert kept.status_code == 200, kept.text
    return [frase["frase_id"] for frase in await frases_read_by_b(room, session_id)]


async def read_by_b(room: Room, session_id: str) -> list[dict[str, Any]]:
    listed = await room.client.get(
        f"{IR}/sessions/{session_id}/scene-rehearsals", headers=room.tablet_b
    )
    assert listed.status_code == 200, listed.text
    return list(listed.json()["scene_rehearsals"])


async def frases_read_by_b(room: Room, session_id: str) -> list[dict[str, Any]]:
    (rehearsal,) = await read_by_b(room, session_id)
    return list(rehearsal["frases"])


async def count(db: AsyncSession, table: str, column: str, value: str) -> int:
    found = await db.execute(
        text(f"SELECT count(*) FROM {table} WHERE {column} = :v"), {"v": value}
    )
    return int(found.scalar_one())


async def write(db: AsyncSession, column: str, value: str | None, rehearsal_id: str) -> None:
    await db.execute(
        text(f"UPDATE ir_scene_rehearsals SET {column} = :v WHERE id = :id"),
        {"v": value, "id": rehearsal_id},
    )
    await db.commit()


async def sent(db: AsyncSession, rehearsal_id: str) -> None:
    """The rehearsal sent: stamped under a turn id whose reply was stored."""
    from app.services.internalization_room.turn_dedup import remember_turn

    session_id = (
        await db.execute(
            text("SELECT session_id FROM ir_scene_rehearsals WHERE id = :id"), {"id": rehearsal_id}
        )
    ).scalar_one()
    await remember_turn(db, session_id=session_id, turn_id="turno-da-cena", response={})
    await write(db, "sent_turn_id", "turno-da-cena", rehearsal_id)
    await write(db, "sent_at", "2026-10-13 09:00:00", rehearsal_id)


def key_of(room: Room, audio: bytes) -> str:
    (key,) = [key for key, stored in room.bucket.objects.items() if stored == audio]
    return key


async def restart(
    room: Room,
    session_id: str,
    rehearsal_id: str,
    attempt: str | None = None,
    *,
    closes: str | None = None,
) -> httpx.Response:
    data = {"attempt": attempt or str(uuid.uuid4())}
    if closes is not None:
        data["closes"] = closes
    return await room.client.post(
        f"{IR}/sessions/{session_id}/scene-rehearsals/{rehearsal_id}/restart", data=data
    )
