"""The analyst reads the whole telling-back, or it does not read at all.

Its prompt defines a missing element as *one that appears in no stretch*, and forbids linking
one stretch to another. So handing it a subset contradicts the definition it works by:
everything that lived in the stretch left out comes back as missing, and the team is told about
a hole they are on their way to filling.

The only way to have a final stretch with no explanation is to replace a stretch's mother-tongue
recording, which starts it over with nothing the team said — so this gate is preventive today
and load-bearing the minute that route exists.

These cases describe what the room does, never how it is stored: none of them names a table or
a column.
"""

from __future__ import annotations

import base64
import importlib
import json
from typing import Any

import httpx
import pytest
from google_crc32c import Checksum
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSegment, IRTakeKind
from app.services.internalization_room import segments as service
from app.services.internalization_room.fail_safe import FailSafe
from app.services.internalization_room.sessions import get_session
from app.services.platform.storage import StoredObject

PREFIX = "/api/internalization-room"
KEY = "sala-de-teste"
DEVICE = "tablet-da-equipe-1"
PASSAGE = "P01"


class MemoryStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def get(self, key: str) -> bytes | None:
        return self.objects.get(key)

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = data

    async def stat(self, key: str) -> StoredObject | None:
        stored = self.objects.get(key)
        if stored is None:
            return None
        checksum = Checksum()
        checksum.update(stored)
        return StoredObject(
            size=len(stored), crc32c=base64.b64encode(checksum.digest()).decode("ascii")
        )


class Analyst:
    """The analyst, and a count of how many times it was actually asked to read.

    The count is the point of half these cases: "did not run" is not observable from the
    answer alone, because a clean reading and no reading at all produce the same verdict.
    """

    def __init__(self) -> None:
        self.readings = 0

    async def __call__(self, *, system_prompt: str, user_content: str, **_: Any) -> str:
        self.readings += 1
        return '{"evidence_sufficient": true, "findings": []}'


@pytest.fixture()
async def bucket(monkeypatch: pytest.MonkeyPatch) -> MemoryStore:
    from app.services.internalization_room import takes as takes_service

    store = MemoryStore()
    monkeypatch.setattr(takes_service, "_store", lambda *_, **__: store)
    return store


@pytest.fixture()
def analyst(monkeypatch: pytest.MonkeyPatch) -> Analyst:
    from app.services.internalization_room import back_translation as bt_service

    reader = Analyst()
    monkeypatch.setattr(bt_service, "call_agent", reader)
    return reader


@pytest.fixture(autouse=True)
def a_room_that_can_speak(monkeypatch: pytest.MonkeyPatch) -> None:
    """The verdict speaker and the voice, so a case that reaches them reaches them fully.

    A case that expects no verdict has to be refused by the gate, not by a missing model.
    """
    from app.api.internalization_room import back_translation as bt_api

    # The package re-exports a `run_turn` function under the submodule's own name, so the
    # module has to be asked for by path rather than by attribute.
    turn_module = importlib.import_module("app.services.internalization_room.run_turn")

    async def speaker(*, system_prompt: str, user_content: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return "Vocês contaram bem."

    monkeypatch.setattr(turn_module, "call_agent", speaker)

    async def _voice(*_: Any, **__: Any):
        return (type("Voiced", (), {"key": "uma-chave"})(), 0)

    monkeypatch.setattr(bt_api.room, "synthesize_facilitator_speech", _voice)


@pytest.fixture()
async def client(db_session: AsyncSession, bucket: MemoryStore, monkeypatch: pytest.MonkeyPatch):
    from fastapi import FastAPI

    from app.api.internalization_room import back_translation as bt_api
    from app.api.internalization_room import router
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    monkeypatch.setattr(get_settings(), "internalization_room_api_key", KEY, raising=False)

    said: list[str] = []

    async def _transcribe(*_: Any, **__: Any) -> str:
        return said.pop(0) if said else "algo que a equipe contou"

    monkeypatch.setattr(bt_api, "heard", _transcribe)

    test_app = FastAPI()
    test_app.include_router(router, prefix=PREFIX)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        c.said = said  # type: ignore[attr-defined]
        yield c


async def _open_session(client: httpx.AsyncClient) -> str:
    created = await client.post(
        f"{PREFIX}/sessions", headers={"X-Room-Key": KEY}, json={"pericope": PASSAGE}
    )
    assert created.status_code == 200, created.text
    return str(created.json()["session_id"])


async def _record(client: httpx.AsyncClient, session_id: str, audio: bytes) -> str:
    kept = await client.post(
        f"{PREFIX}/sessions/{session_id}/takes",
        headers={"X-Room-Key": KEY, "X-Room-Device": DEVICE},
        data={"kind": IRTakeKind.ENSAIO.value, "scope": PASSAGE},
        files={"file": ("tomada.m4a", audio, "audio/mp4")},
    )
    assert kept.status_code == 200, kept.text
    return str(kept.json()["take_id"])


async def _tell_back(
    client: httpx.AsyncClient,
    session_id: str,
    *,
    take_id: str,
    starts_ms: int,
    ends_ms: int,
    audio: bytes,
) -> None:
    told = await client.post(
        f"{PREFIX}/sessions/{session_id}/back-translation/chunks",
        headers={"X-Room-Key": KEY, "X-Room-Device": DEVICE},
        data={"take_id": take_id, "starts_ms": str(starts_ms), "ends_ms": str(ends_ms)},
        files={"file": ("trecho.m4a", audio, "audio/mp4")},
    )
    assert told.status_code == 200, told.text


async def _finish(client: httpx.AsyncClient, session_id: str) -> httpx.Response:
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/back-translation/finish", headers={"X-Room-Key": KEY}
    )


async def _two_stretches_told(client: httpx.AsyncClient) -> tuple[str, str]:
    session_id = await _open_session(client)
    take_id = await _record(client, session_id, b"a equipe ensaiou a passagem inteira")
    client.said.extend(["Noemi mandou Rute voltar.", "Rute disse que ia junto."])  # type: ignore[attr-defined]
    await _tell_back(
        client, session_id, take_id=take_id, starts_ms=0, ends_ms=9000, audio=b"primeiro trecho"
    )
    await _tell_back(
        client, session_id, take_id=take_id, starts_ms=9000, ends_ms=21000, audio=b"segundo trecho"
    )
    return session_id, take_id


async def _re_record_the_native(db: AsyncSession, session_id: str, *, take_id: str) -> IRSegment:
    """Redo one stretch's mother-tongue audio, which is what leaves it waiting to be told.

    The service refuses to carry the old explanation across when the slice moves — the
    explanation belonged to audio nobody will hear again — so the stretch comes back with
    nothing the team said, which is exactly the state this gate is about.
    """
    session = await get_session(db, session_id)
    standing = await service.final_segments(db, session_id)
    return await service.capture_segment(
        db,
        session,
        take_id=take_id,
        starts_ms=9000,
        ends_ms=24000,
        replaces=standing[-1],
    )


async def _explain(db: AsyncSession, session_id: str, segment: IRSegment) -> IRSegment:
    """Give a waiting stretch its telling-back, without moving the recording under it."""
    session = await get_session(db, session_id)
    return await service.capture_segment(
        db,
        session,
        take_id=segment.take_id,
        starts_ms=segment.starts_ms,
        ends_ms=segment.ends_ms,
        bridge_take_id="retro-novo",
        transcript="Rute disse que ia junto, e foi.",
        replaces=segment,
    )


@pytest.mark.asyncio
async def test_a_stretch_still_waiting_stops_the_analyst_from_reading(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: Analyst
) -> None:
    """Scenario 1. Half the work is not the work, and the analyst is never shown half.

    Its prompt calls an element missing when it appears in no stretch, so a subset makes it
    raise findings about the stretch that was left out.
    """
    session_id, take_id = await _two_stretches_told(client)
    await _re_record_the_native(db_session, session_id, take_id=take_id)

    answered = await _finish(client, session_id)

    assert answered.status_code == 200, answered.text
    assert analyst.readings == 0, (
        "o analista não pode ler um subconjunto: a definição de 'faltando' que ele usa é "
        "sobre a retrotradução inteira"
    )


@pytest.mark.asyncio
async def test_the_room_tells_the_team_instead_of_going_quiet(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: Analyst
) -> None:
    """Scenario 2. A refusal the team cannot hear is a room that stopped working."""
    session_id, take_id = await _two_stretches_told(client)
    await _re_record_the_native(db_session, session_id, take_id=take_id)

    answered = await _finish(client, session_id)
    body = answered.json()

    assert body["fixed_line"].startswith(str(FailSafe.UNTOLD_STRETCH)), (
        "a fala tem de ser a desta situação: a família de 'não consegui ouvir' mente, porque "
        "a sala ouviu tudo, e manda repetir o que já foi contado em vez de contar o que falta"
    )
    assert body["audio_url"] == "", "fala pré-aprovada e url nunca vêm juntas"


@pytest.mark.asyncio
async def test_the_passage_is_not_marked_checked_over_a_stretch_nobody_explained(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: Analyst
) -> None:
    """Scenario 3, and the one the slice exists for.

    A clean reading of a subset is indistinguishable from a clean reading of the whole, and
    `checked` is what the app strikes the passage off the wheel by. A finished passage never
    comes back, so there is no undoing this one.
    """
    session_id, take_id = await _two_stretches_told(client)
    await _re_record_the_native(db_session, session_id, take_id=take_id)

    answered = await _finish(client, session_id)

    assert answered.json()["checked"] is False
    standing = await client.get(f"{PREFIX}/sessions/{session_id}", headers={"X-Room-Key": KEY})
    assert standing.json()["back_translation"]["checked"] is False, (
        "e não pode ter avançado no estado que o tablet retoma depois"
    )


@pytest.mark.asyncio
async def test_the_gate_opens_itself_when_the_last_stretch_is_explained(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: Analyst
) -> None:
    """Scenario 4. Nobody unlocks anything: the condition stops holding and the reading runs."""
    session_id, take_id = await _two_stretches_told(client)
    waiting = await _re_record_the_native(db_session, session_id, take_id=take_id)
    assert (await _finish(client, session_id)).json()["checked"] is False

    await _explain(db_session, session_id, waiting)
    answered = await _finish(client, session_id)

    assert analyst.readings == 1, "a leitura roda assim que a retrotradução está inteira"
    assert answered.json()["checked"] is True


@pytest.mark.asyncio
async def test_a_telling_back_with_every_stretch_explained_is_read_as_before(
    client: httpx.AsyncClient, analyst: Analyst
) -> None:
    """Scenario 5. Regression: the ordinary path gets no slower and no narrower."""
    session_id, _take_id = await _two_stretches_told(client)

    answered = await _finish(client, session_id)
    body = answered.json()

    assert analyst.readings == 1
    assert body["checked"] is True
    assert body["fixed_line"] == "", "o caminho normal fala pela síntese, não por fala fixa"


@pytest.mark.asyncio
async def test_a_telling_back_with_no_stretch_at_all_answers_as_before(
    client: httpx.AsyncClient, analyst: Analyst
) -> None:
    """Scenario 6. There is already a path for this one, and it is not this one.

    Nothing was told back, so the honest thing is that the room heard nothing — not that a
    stretch is waiting, because there is no stretch.
    """
    session_id = await _open_session(client)

    answered = await _finish(client, session_id)
    body = answered.json()

    assert analyst.readings == 0
    assert body["checked"] is False
    assert body["fixed_line"].startswith(str(FailSafe.INAUDIBLE))
