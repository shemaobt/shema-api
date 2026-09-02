"""When a stretch was never told back, the room says which one.

The gate that stops the analyst reading half a telling-back already worked: it counts the
stretches that count against the stretches the team explained, and when the second number is
smaller it speaks the waiting line instead of a verdict. What it never did was say *which*
stretch is waiting.

An answer with no address leaves the app one move: send the team back to the rehearsal screen,
which throws away every recording of the passage. The team loses a morning over one missing
explanation. The address is what makes the smaller move possible.

First in the order of the passage, not any of them: a team tells a passage in sequence, and
being sent to a hole in the middle while an earlier one is still open inverts the order of
their own work.

These cases describe what the room answers, never how it is stored: none of them names a table
or a column.
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
from app.services.internalization_room.fail_safe import FailSafe, utterances
from app.services.internalization_room.sessions import get_session
from app.services.platform.storage import StoredObject

PREFIX = "/api/internalization-room"
KEY = "sala-de-teste"
DEVICE = "tablet-da-equipe-1"
PASSAGE = "P01"
LANGUAGE = "pt"


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

    A waiting stretch has to be answered before the reading, and "did not run" is not
    readable from the answer alone: a clean reading and no reading at all agree on every
    field but this counter.
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
def spoken(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Every line the room was asked to say, and a voice that does not need the network.

    Kept because the answer carries an address and a clip name: what was actually said is
    not readable from the response at all.
    """
    said_aloud: list[str] = []

    from app.api.internalization_room import back_translation as bt_api

    turn_module = importlib.import_module("app.services.internalization_room.run_turn")

    async def speaker(*, system_prompt: str, user_content: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return "Vocês contaram bem."

    monkeypatch.setattr(turn_module, "call_agent", speaker)

    async def _voice(text: str, *_: Any, **__: Any):
        said_aloud.append(text)
        return (type("Voiced", (), {"key": f"clipe-{len(said_aloud)}"})(), 0)

    monkeypatch.setattr(bt_api.room, "synthesize_facilitator_speech", _voice)
    return said_aloud


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
        f"{PREFIX}/sessions",
        headers={"X-Room-Key": KEY},
        json={"pericope": PASSAGE, "language": LANGUAGE},
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


async def _three_stretches_told(client: httpx.AsyncClient) -> str:
    """A passage told back in three stretches, in the order the team told them."""
    session_id = await _open_session(client)
    take_id = await _record(client, session_id, b"a equipe ensaiou a passagem inteira")
    client.said.extend(  # type: ignore[attr-defined]
        [
            "Noemi mandou Rute voltar.",
            "Rute disse que ia junto.",
            "As duas chegaram a Belém.",
        ]
    )
    for starts_ms, ends_ms in ((0, 9000), (9000, 21000), (21000, 30000)):
        await _tell_back(
            client,
            session_id,
            take_id=take_id,
            starts_ms=starts_ms,
            ends_ms=ends_ms,
            audio=b"um trecho",
        )
    return session_id


async def _standing(db: AsyncSession, session_id: str) -> list[IRSegment]:
    """The stretches that count right now, in the order of the passage."""
    return await service.final_segments(db, session_id)


async def _re_record_the_native(db: AsyncSession, session_id: str, segment: IRSegment) -> IRSegment:
    """Redo one stretch's mother-tongue audio, which is what leaves it waiting to be told.

    The service refuses to carry the old explanation across when the slice moves — it
    belonged to audio nobody will hear again — so the stretch comes back with nothing the
    team said, which is the state this file is about.
    """
    session = await get_session(db, session_id)
    return await service.capture_segment(
        db,
        session,
        take_id=segment.take_id,
        starts_ms=segment.starts_ms,
        ends_ms=segment.ends_ms + 1500,
        replaces=segment,
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
async def test_the_room_names_the_stretch_that_was_never_told_back(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: Analyst
) -> None:
    """Case 1. The answer carries the address of the stretch that is waiting.

    Without it the app has nowhere to send the team but the beginning, and the beginning
    costs them every recording of the passage.
    """
    session_id = await _three_stretches_told(client)
    standing = await _standing(db_session, session_id)
    waiting = await _re_record_the_native(db_session, session_id, standing[1])

    body = (await _finish(client, session_id)).json()

    assert body["untold_segment_id"] == waiting.id, (
        "a resposta tem de dizer qual trecho falta, e não apenas que falta algum"
    )


@pytest.mark.asyncio
async def test_the_stretch_named_is_the_first_one_in_the_order_of_the_passage(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: Analyst
) -> None:
    """Case 2. With more than one hole open, the team is sent to the earliest of them.

    The later stretch is re-recorded first on purpose: the order the rows were written in is
    the reverse of the order the team tells in, so an answer that reads back the newest row,
    or any row at all, is not the same as an answer that reads the passage.
    """
    session_id = await _three_stretches_told(client)
    standing = await _standing(db_session, session_id)
    later = await _re_record_the_native(db_session, session_id, standing[2])
    earlier = await _re_record_the_native(db_session, session_id, standing[0])

    body = (await _finish(client, session_id)).json()

    assert body["untold_segment_id"] == earlier.id, (
        "a equipe conta a passagem na sequência dela; mandá-la para um buraco no meio "
        "enquanto há um anterior aberto inverte a ordem do próprio trabalho"
    )
    assert body["untold_segment_id"] != later.id


@pytest.mark.asyncio
async def test_naming_the_stretch_does_not_turn_the_waiting_into_a_verdict(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: Analyst, spoken: list[str]
) -> None:
    """Case 3. The gate that was already right stays right.

    An address is a smaller move for the app, not permission to call the passage checked:
    the analyst still never sees a subset, the team still hears the waiting line, and
    `checked` — which is what the app strikes the passage off the wheel by — stays false.
    """
    session_id = await _three_stretches_told(client)
    standing = await _standing(db_session, session_id)
    await _re_record_the_native(db_session, session_id, standing[1])

    body = (await _finish(client, session_id)).json()

    assert body["untold_segment_id"] is not None
    assert body["checked"] is False, "um endereço não é uma passagem conferida"
    assert body["finding_kind"] is None, "e não é um achado do analista, que nem rodou"
    assert body["finding_segment_id"] is None, (
        "os dois endereços nunca vêm juntos: o app tem de saber qual dos dois casos é sem "
        "inferir um pela ausência do outro"
    )
    assert analyst.readings == 0, "o analista continua sem ver um subconjunto"
    assert body["audio_url"], "a equipe continua tendo o que tocar"
    assert spoken[-1] in utterances(FailSafe.UNTOLD_STRETCH, LANGUAGE), (
        "a linha falada continua sendo a da família H, palavra por palavra"
    )


@pytest.mark.asyncio
async def test_a_telling_back_with_every_stretch_told_names_no_stretch(
    client: httpx.AsyncClient, analyst: Analyst
) -> None:
    """Case 4. The ordinary path is untouched: a verdict, and no address."""
    session_id = await _three_stretches_told(client)

    body = (await _finish(client, session_id)).json()

    assert body["untold_segment_id"] is None
    assert body["checked"] is True
    assert analyst.readings == 1


@pytest.mark.asyncio
async def test_a_stretch_that_was_replaced_is_never_named_as_the_missing_one(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: Analyst
) -> None:
    """Case 5. A version that stopped counting is not a hole, even though it never got a text.

    Re-recording a stretch's native audio and then explaining it leaves a retired row with no
    telling-back on it forever. It is not waiting for anything — the team already told it, on
    the row that took its place — and sending them back to it would be sending them to work
    they have finished.
    """
    session_id = await _three_stretches_told(client)
    standing = await _standing(db_session, session_id)

    retired_with_no_telling = await _re_record_the_native(db_session, session_id, standing[0])
    await _explain(db_session, session_id, retired_with_no_telling)
    still_waiting = await _re_record_the_native(db_session, session_id, standing[2])

    body = (await _finish(client, session_id)).json()

    assert body["untold_segment_id"] == still_waiting.id
    assert body["untold_segment_id"] != retired_with_no_telling.id, (
        "uma versão retirada não é um trecho por contar: quem só olha a tabela crua manda "
        "a equipe refazer o que ela já refez"
    )


@pytest.mark.asyncio
async def test_a_stretch_divided_in_two_is_named_by_its_first_half(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: Analyst
) -> None:
    """Hardening beyond the plan: dividing is the other way a hole opens.

    A stretch split in two hands back two halves with nothing the team said on either, and
    the halves stand where their parent stood. So the order of the passage stops being a
    column and becomes a walk: the first half of the first stretch comes before a stretch
    that was already there, even though it was written to the table last.
    """
    session_id = await _three_stretches_told(client)
    standing = await _standing(db_session, session_id)
    await _re_record_the_native(db_session, session_id, standing[2])
    session = await get_session(db_session, session_id)
    head, tail = await service.divide_segment(db_session, session, standing[0], at_ms=4000)

    body = (await _finish(client, session_id)).json()

    assert body["untold_segment_id"] == head.id
    assert body["untold_segment_id"] != tail.id, (
        "a metade da frente vem antes da de trás, e as duas vêm antes do que já estava lá"
    )
