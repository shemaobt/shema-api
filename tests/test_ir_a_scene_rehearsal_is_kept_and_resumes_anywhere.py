"""ENG-1312 — a scene rehearsal is kept on the server and resumes on any tablet of the team.

The team records a whole scene in its mother tongue and translates it frase by frase. The
server keeps one record per **Scene rehearsal**: the recording, never heard by the recognizer,
the **Scene frases** with their places, the sent stamp and the team's scene label apart from
the classifier's guess. Two tablets of one team speak through the real doors. The cases that
say a row, a stamp or an object exists read the tables and the bucket, because that is what
they assert.
"""

from __future__ import annotations

import io
import json
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


def current(frases: list[dict[str, Any]]) -> list[tuple[int, int]]:
    return [(f["starts_ms"], f["ends_ms"]) for f in frases if f["replaced_by"] is None]


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


async def test_an_unsent_rehearsal_opened_on_another_tablet_resumes_after_frase_3(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    await translated(room, session_id, rehearsal_id, [(0, 5000), (5000, 11000), (11000, 17000)])

    (rehearsal,) = await read_by_b(room, session_id)

    assert rehearsal["rehearsal_id"] == rehearsal_id
    assert rehearsal["sent_at"] is None
    assert current(rehearsal["frases"]) == [(0, 5000), (5000, 11000), (11000, 17000)]
    heard_on_b = await room.client.get(
        f"{IR}/sessions/{session_id}/scene-rehearsals/{rehearsal_id}/audio",
        headers=room.tablet_b,
    )
    assert heard_on_b.status_code == 307, heard_on_b.text
    assert room.signed == [key_of(room, SCENE)]


async def test_a_last_frase_replaced_on_one_tablet_is_the_one_the_other_tablet_reads(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    *_, third = await translated(
        room, session_id, rehearsal_id, [(0, 5000), (5000, 11000), (11000, 17000)]
    )

    moved = await translate(
        room, session_id, rehearsal_id, (11000, 18500), recording(1, 900), replaces=third
    )

    assert moved.status_code == 200, moved.text
    frases = await frases_read_by_b(room, session_id)
    assert current(frases) == [(0, 5000), (5000, 11000), (11000, 18500)]
    replacing = next(f["frase_id"] for f in frases if f["ends_ms"] == 18500)
    assert {f["frase_id"]: f["replaced_by"] for f in frases}[third] == replacing


@pytest.mark.parametrize(
    ("place", "code"),
    [
        pytest.param((None, 5000), None, id="no starts_ms"),
        pytest.param((5000, 5000), "FRASE_OUT_OF_PLACE", id="ends_ms not after starts_ms"),
        pytest.param((30000, 41000), "FRASE_OUT_OF_PLACE", id="ends_ms beyond the recording"),
    ],
)
async def test_a_frase_with_no_place_in_the_recording_is_refused_and_the_record_keeps_no_frase(
    room: Room,
    db_session: AsyncSession,
    place: tuple[int | None, int | None],
    code: str | None,
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)

    refused = await translate(room, session_id, rehearsal_id, place, recording(1, 100))

    assert refused.status_code == 422, refused.text
    assert refused.json().get("code") == code
    assert await frases_read_by_b(room, session_id) == []


async def test_a_zerar_stamps_the_passages_scene_rehearsals_and_their_frases(
    room: Room, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    a_scripted_room(monkeypatch)
    session_id = await a_session(db_session, language="pt")
    rehearsal_id = await recorded(room, session_id)
    await translated(room, session_id, rehearsal_id, [(0, 5000), (5000, 11000)])

    archive_id = await zerar(room)

    opened = await the_tablet_opens(room.client, room.credential, {"pericope": P, "language": "pt"})
    assert opened["session_id"] != session_id
    assert await read_by_b(room, opened["session_id"]) == []
    assert await stamps(db_session, "ir_scene_rehearsals", "id", rehearsal_id) == [archive_id]
    assert await stamps(db_session, "ir_scene_frases", "rehearsal_id", rehearsal_id) == [
        archive_id,
        archive_id,
    ]


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


async def test_the_same_frase_sent_twice_is_one_frase(room: Room, db_session: AsyncSession) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    frase = recording(1, 100)
    assert (await translate(room, session_id, rehearsal_id, (0, 5000), frase)).status_code == 200

    again = await translate(room, session_id, rehearsal_id, (0, 5000), frase)

    assert again.status_code == 200, again.text
    assert current(await frases_read_by_b(room, session_id)) == [(0, 5000)]
    assert await count(db_session, "ir_scene_frases", "rehearsal_id", rehearsal_id) == 1


async def test_a_frase_with_no_words_is_refused_and_becomes_no_frase(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session, language="pt")
    rehearsal_id = await recorded(room, session_id)
    frase = recording(1, 100)
    room.answers.append("")

    refused = await translate(room, session_id, rehearsal_id, (0, 5000), frase)

    assert refused.status_code == 422, refused.text
    assert refused.json()["code"] == "WORDLESS_TELLING"
    assert await frases_read_by_b(room, session_id) == []
    assert frase in room.bucket.objects.values()
    assert [call.get("language") for call in room.heard] == ["pt"]


async def test_a_sent_rehearsal_takes_no_frase_and_is_still_heard(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    await write(db_session, "sent_at", "2026-10-13 09:00:00", rehearsal_id)

    frase = await translate(room, session_id, rehearsal_id, (0, 5000), recording(1, 100))

    assert frase.status_code == 409, frase.text
    (listed,) = await read_by_b(room, session_id)
    assert listed["rehearsal_id"] == rehearsal_id
    assert listed["sent_at"] is not None
    heard = await room.client.get(
        f"{IR}/sessions/{session_id}/scene-rehearsals/{rehearsal_id}/audio"
    )
    assert heard.status_code == 307, heard.text


async def test_a_frase_may_not_replace_another_rehearsals_frase(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    other_id = await recorded(room, session_id, recording(10, 2))
    kept = await translate(room, session_id, other_id, (0, 5000), recording(1, 500))
    assert kept.status_code == 200, kept.text
    (other,) = [
        f["frase_id"]
        for r in await read_by_b(room, session_id)
        if r["rehearsal_id"] == other_id
        for f in r["frases"]
    ]
    before = await read_by_b(room, session_id)

    refused = await translate(
        room, session_id, rehearsal_id, (0, 7000), recording(1, 901), replaces=other
    )

    assert refused.status_code == 422, refused.text
    assert refused.json()["code"] == "UNKNOWN_REFERENCE"
    assert await read_by_b(room, session_id) == before


async def test_a_frase_sent_offline_against_an_earlier_version_replaces_the_current_one(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    (first,) = await translated(room, session_id, rehearsal_id, [(0, 5000)], tone=300)
    again = await translate(
        room, session_id, rehearsal_id, (0, 6000), recording(1, 900), replaces=first
    )
    assert again.status_code == 200, again.text

    third = await translate(
        room, session_id, rehearsal_id, (0, 7000), recording(1, 901), replaces=first
    )

    assert third.status_code == 200, third.text
    frases = await frases_read_by_b(room, session_id)
    assert current(frases) == [(0, 7000)]
    by_end = {f["ends_ms"]: f for f in frases}
    assert by_end[6000]["replaced_by"] == by_end[7000]["frase_id"]
    assert by_end[7000]["replaces"] == by_end[6000]["frase_id"]


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


async def test_a_frase_heard_while_the_rehearsal_is_sent_is_refused(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)

    async def send() -> None:
        await write(db_session, "sent_at", "2026-10-13 09:00:00", rehearsal_id)

    room.while_hearing.append(send)
    late = await translate(room, session_id, rehearsal_id, (0, 5000), recording(1, 700))

    assert late.status_code == 409, late.text
    assert await count(db_session, "ir_scene_frases", "rehearsal_id", rehearsal_id) == 0


async def test_a_frase_heard_while_the_passage_is_zerada_carries_the_archive_stamp(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    archived: list[str] = []

    async def zera() -> None:
        archived.append(await zerar(room))

    room.while_hearing.append(zera)
    await translate(room, session_id, rehearsal_id, (0, 5000), recording(1, 700))

    assert await stamps(db_session, "ir_scene_frases", "rehearsal_id", rehearsal_id) == archived


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


async def restart(
    room: Room, session_id: str, rehearsal_id: str, *, key: str | None = None
) -> httpx.Response:
    return await room.client.post(
        f"{IR}/sessions/{session_id}/scene-rehearsals/{rehearsal_id}/restart",
        headers={} if key is None else {"Idempotency-Key": key},
    )


async def restarted(room: Room, session_id: str, rehearsal_id: str) -> str:
    answered = await restart(room, session_id, rehearsal_id)
    assert answered.status_code == 200, answered.text
    return str(answered.json()["after_restart"])


async def translate_after(
    room: Room,
    session_id: str,
    rehearsal_id: str,
    place: tuple[int, int],
    audio: bytes,
    after_restart: str,
) -> httpx.Response:
    starts, ends = place
    return await room.client.post(
        f"{IR}/sessions/{session_id}/scene-rehearsals/{rehearsal_id}/frases",
        data={"starts_ms": str(starts), "ends_ms": str(ends), "after_restart": after_restart},
        files={"file": ("frase.wav", audio, "audio/wav")},
    )


async def snapshots(db: AsyncSession, rehearsal_id: str) -> list[dict[str, Any]]:
    found = await db.execute(
        text("SELECT snapshot FROM ir_scene_restarts WHERE rehearsal_id = :r ORDER BY n"),
        {"r": rehearsal_id},
    )
    return [json.loads(row) if isinstance(row, str) else row for row in found.scalars()]


async def test_recomecar_after_two_frases_archives_them_with_the_record_as_it_was(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    two = await translated(room, session_id, rehearsal_id, [(0, 5000), (5000, 11000)])

    answered = await restart(room, session_id, rehearsal_id)

    assert answered.status_code == 200, answered.text
    (rehearsal,) = await read_by_b(room, session_id)
    assert rehearsal["frases"] == []
    assert rehearsal["after_restart"] == answered.json()["after_restart"]
    assert (rehearsal["rehearsal_id"], rehearsal["n"]) == (rehearsal_id, 1)
    assert abs(rehearsal["duration_ms"] - 40_000) <= 50
    (snapshot,) = await snapshots(db_session, rehearsal_id)
    assert [f["frase_id"] for f in snapshot["frases"]] == two
    assert await count(db_session, "ir_scene_frases", "rehearsal_id", rehearsal_id) == 2
    kept = list(room.bucket.objects.values())
    assert recording(1, 100) in kept and recording(1, 101) in kept
    assert SCENE in kept


async def test_the_same_restart_sent_twice_is_one_restart(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    await translated(room, session_id, rehearsal_id, [(0, 5000)])
    first = await restart(room, session_id, rehearsal_id, key="recomecar-1")
    assert first.status_code == 200, first.text
    after = first.json()["after_restart"]
    kept = await translate_after(
        room, session_id, rehearsal_id, (0, 4000), recording(1, 800), after
    )
    assert kept.status_code == 200, kept.text

    again = await restart(room, session_id, rehearsal_id, key="recomecar-1")

    assert again.status_code == 200, again.text
    assert again.json()["after_restart"] == after
    assert await count(db_session, "ir_scene_restarts", "rehearsal_id", rehearsal_id) == 1
    assert current(await frases_read_by_b(room, session_id)) == [(0, 4000)]


async def test_a_frase_recorded_before_a_restart_and_sent_after_it_is_set_aside(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    await translated(room, session_id, rehearsal_id, [(0, 5000)])
    after = await restarted(room, session_id, rehearsal_id)

    late = await translate(room, session_id, rehearsal_id, (5000, 11000), recording(1, 600))
    fresh = await translate_after(
        room, session_id, rehearsal_id, (0, 4000), recording(1, 601), after
    )

    assert late.status_code == 200, late.text
    assert fresh.status_code == 200, fresh.text
    assert current(await frases_read_by_b(room, session_id)) == [(0, 4000)]
    assert await count(db_session, "ir_scene_frases", "restart_id", after) == 2


async def test_a_frase_heard_while_the_translation_restarts_is_set_aside_with_the_ones_before_it(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    await translated(room, session_id, rehearsal_id, [(0, 5000)])

    async def recomeca() -> None:
        await restarted(room, session_id, rehearsal_id)

    room.while_hearing.append(recomeca)
    late = await translate(room, session_id, rehearsal_id, (5000, 11000), recording(1, 700))

    assert late.status_code == 200, late.text
    assert await frases_read_by_b(room, session_id) == []
    assert await count(db_session, "ir_scene_frases", "rehearsal_id", rehearsal_id) == 2


async def test_a_frase_naming_a_restart_the_rehearsal_never_had_is_refused(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)

    refused = await translate_after(
        room, session_id, rehearsal_id, (0, 4000), recording(1, 600), str(uuid.uuid4())
    )

    assert refused.status_code == 422, refused.text
    assert refused.json()["code"] == "UNKNOWN_REFERENCE"
    assert await frases_read_by_b(room, session_id) == []


async def test_a_sent_rehearsal_takes_no_restart(room: Room, db_session: AsyncSession) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    await write(db_session, "sent_at", "2026-10-13 09:00:00", rehearsal_id)

    refused = await restart(room, session_id, rehearsal_id)

    assert refused.status_code == 409, refused.text
    assert await count(db_session, "ir_scene_restarts", "rehearsal_id", rehearsal_id) == 0


async def test_a_zerar_stamps_the_scene_rehearsals_restarts(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    await translated(room, session_id, rehearsal_id, [(0, 5000), (5000, 11000)])
    await restarted(room, session_id, rehearsal_id)

    archive_id = await zerar(room)

    assert await stamps(db_session, "ir_scene_restarts", "rehearsal_id", rehearsal_id) == [
        archive_id
    ]
    assert await stamps(db_session, "ir_scene_frases", "rehearsal_id", rehearsal_id) == [
        archive_id,
        archive_id,
    ]
