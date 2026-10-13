"""ENG-1312 — a scene rehearsal is kept on the server and resumes on any tablet of the team.

The team records a whole scene in its mother tongue and translates it frase by frase. The
server keeps one record per **Scene rehearsal**: the recording, never heard by the recognizer,
the **Scene frases** with their places, the sent stamp and the team's scene label apart from
the classifier's guess. Two tablets of one team speak through the real doors. The cases that
say a row, a stamp or an object exists read the tables and the bucket, because that is what
they assert.
"""

from __future__ import annotations

import asyncio
import io
import uuid
import wave
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import event, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ProjectRole
from app.db.models.auth import Role
from app.services.internalization_room.sessions import create_session, get_session
from tests.baker import make_app, make_project_user_access, make_role, make_user, make_user_app_role
from tests.device_harness import TABLET_TEAM, a_linked_tablet
from tests.hard_stretch_harness import MemoryStore, a_session
from tests.opening_harness import a_scripted_room, the_tablet_opens

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


@pytest.fixture()
async def room(db_session: AsyncSession, rival_factory, monkeypatch: pytest.MonkeyPatch):
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


async def read_by_b(room: Room, session_id: str) -> list[dict[str, Any]]:
    listed = await room.client.get(
        f"{IR}/sessions/{session_id}/scene-rehearsals", headers=room.tablet_b
    )
    assert listed.status_code == 200, listed.text
    return list(listed.json()["scene_rehearsals"])


async def zerar(room: Room) -> str:
    zerado = await room.client.post(
        f"{IR}/facilitator/projects/{TABLET_TEAM}/passages/{P}/archive", headers=room.desk
    )
    assert zerado.status_code == 200, zerado.text
    return str(zerado.json()["archive"]["id"])


async def count(db: AsyncSession, table: str, column: str, value: str) -> int:
    found = await db.execute(
        text(f"SELECT count(*) FROM {table} WHERE {column} = :v"), {"v": value}
    )
    return int(found.scalar_one())


async def stamps(db: AsyncSession, table: str, column: str, value: str) -> list[str | None]:
    found = await db.execute(
        text(f"SELECT archive_id FROM {table} WHERE {column} = :v"), {"v": value}
    )
    return list(found.scalars())


async def write(db: AsyncSession, column: str, value: str | None, rehearsal_id: str) -> None:
    await db.execute(
        text(f"UPDATE ir_scene_rehearsals SET {column} = :v WHERE id = :id"),
        {"v": value, "id": rehearsal_id},
    )
    await db.commit()


def key_of(room: Room, audio: bytes) -> str:
    (key,) = [key for key, stored in room.bucket.objects.items() if stored == audio]
    return key


async def test_a_40_second_scene_recording_is_kept_for_its_session_and_scene_and_never_reaches_the_recognizer(  # noqa: E501
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)

    kept = await record(room, session_id)

    assert kept.status_code == 200, kept.text
    body = kept.json()
    assert body["session_id"] == session_id
    assert body["pericope"] == P
    assert abs(body["duration_ms"] - 40_000) <= 50
    assert await count(db_session, "ir_scene_rehearsals", "session_id", session_id) == 1
    assert SCENE in room.bucket.objects.values()
    assert room.heard == []
    assert await count(db_session, "ir_turns", "session_id", session_id) == 0


async def test_an_unsent_rehearsal_opened_on_another_tablet_is_heard_from_its_own_recording(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)

    (rehearsal,) = await read_by_b(room, session_id)

    assert rehearsal["rehearsal_id"] == rehearsal_id
    assert rehearsal["sent_at"] is None
    heard_on_b = await room.client.get(
        f"{IR}/sessions/{session_id}/scene-rehearsals/{rehearsal_id}/audio",
        headers=room.tablet_b,
    )
    assert heard_on_b.status_code == 307, heard_on_b.text
    assert room.signed == [key_of(room, SCENE)]


async def test_a_zerar_stamps_the_passages_scene_rehearsals(
    room: Room, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    a_scripted_room(monkeypatch)
    session_id = await a_session(db_session, language="pt")
    rehearsal_id = await recorded(room, session_id)

    archive_id = await zerar(room)

    opened = await the_tablet_opens(room.client, room.credential, {"pericope": P, "language": "pt"})
    assert opened["session_id"] != session_id
    assert await read_by_b(room, opened["session_id"]) == []
    assert await stamps(db_session, "ir_scene_rehearsals", "id", rehearsal_id) == [archive_id]


async def test_a_sent_rehearsal_stays_listed_and_is_still_heard(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)

    await write(db_session, "sent_at", "2026-10-13 09:00:00", rehearsal_id)

    (listed,) = await read_by_b(room, session_id)
    assert listed["rehearsal_id"] == rehearsal_id
    assert listed["sent_at"] is not None
    heard = await room.client.get(
        f"{IR}/sessions/{session_id}/scene-rehearsals/{rehearsal_id}/audio"
    )
    assert heard.status_code == 307, heard.text


async def test_a_rehearsal_recorded_for_scene_2_keeps_scene_2_as_the_teams_label_said_at_the_recording(  # noqa: E501
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)

    await write(db_session, "scene_guess", "S3", rehearsal_id)

    (on_the_tablet,) = await read_by_b(room, session_id)
    assert (on_the_tablet["scene"], on_the_tablet["scene_said"]) == ("S2", "recording")
    assert "S3" not in str(on_the_tablet)


async def test_a_scene_that_is_not_one_of_the_passages_is_kept_with_no_label(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)

    kept = await record(room, session_id, scene="S99")

    assert kept.status_code == 200, kept.text
    assert (kept.json()["scene"], kept.json()["scene_said"]) == (None, None)


async def test_a_second_session_of_the_passage_lists_its_live_scene_rehearsals_before_any_turn(
    room: Room, db_session: AsyncSession
) -> None:
    portuguese = await a_session(db_session, language="pt")
    rehearsal_id = await recorded(room, portuguese)
    english = await a_session(db_session, language="en")

    listed = await read_by_b(room, english)

    assert [(r["rehearsal_id"], r["session_id"], r["n"]) for r in listed] == [
        (rehearsal_id, portuguese, 1)
    ]


async def test_the_same_scene_recording_sent_twice_is_one_rehearsal(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    first = (await record(room, session_id)).json()

    again = await record(room, session_id)

    assert again.status_code == 200, again.text
    assert (again.json()["rehearsal_id"], again.json()["n"]) == (first["rehearsal_id"], first["n"])
    assert await count(db_session, "ir_scene_rehearsals", "session_id", session_id) == 1


async def test_a_panorama_session_keeps_no_scene_rehearsal(
    room: Room, db_session: AsyncSession
) -> None:
    panorama = await create_session(
        db_session, project_id=TABLET_TEAM, pericope="OV-Ruth", language="pt"
    )

    kept = await record(room, panorama.id, scene=None)
    listed = await room.client.get(f"{IR}/sessions/{panorama.id}/scene-rehearsals")

    assert kept.status_code == 400, kept.text
    assert kept.json()["code"] == "PANORAMA_RECORDS_NOTHING"
    assert listed.status_code == 400, listed.text
    assert room.bucket.objects == {}


async def test_a_scene_rehearsal_that_lands_after_a_zerar_is_not_listed_for_the_next_session(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    await zerar(room)
    await write(db_session, "archive_id", None, rehearsal_id)
    fresh = await create_session(db_session, pericope=P, project_id=TABLET_TEAM)

    assert await read_by_b(room, fresh.id) == []


async def test_no_statement_of_a_session_read_or_create_names_the_unread_kept_takes(
    room: Room, db_session: AsyncSession, test_engine
) -> None:
    said: list[str] = []

    def _heard(_conn: Any, _cursor: Any, statement: str, *_: Any) -> None:
        said.append(statement)

    event.listen(test_engine.sync_engine, "before_cursor_execute", _heard)
    try:
        session_id = await a_session(db_session)
        await get_session(db_session, session_id)
        await read_by_b(room, session_id)
    finally:
        event.remove(test_engine.sync_engine, "before_cursor_execute", _heard)

    assert any("ir_sessions" in statement for statement in said)
    assert [statement for statement in said if "kept_takes" in statement] == []


async def test_two_scenes_kept_at_once_in_one_session_take_the_next_two_numbers(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)

    first, second = await asyncio.gather(
        record(room, session_id, recording(5, 3)), record(room, session_id, recording(5, 4))
    )

    assert (first.status_code, second.status_code) == (200, 200), (first.text, second.text)
    assert sorted([first.json()["n"], second.json()["n"]]) == [1, 2]


async def test_a_scene_with_no_audio_is_refused_as_no_recording(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)

    refused = await record(room, session_id, b"")

    assert refused.status_code == 400, refused.text
    assert refused.json()["detail"] == "A recording with no audio is not a recording"
