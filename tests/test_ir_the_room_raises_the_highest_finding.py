"""Among one reading's findings the room raises the highest in the **Priority** (ENG-876).

An addition that fills a marked silence, then any other addition, then a missing element,
then an unclear frase. Her own Speaker prompt carries the order in prose, but in her app the
Speaker is handed every finding and picks; in ours the room picks and hands the Speaker
exactly one, so the order has to live here.

It is applied at the pick and never at parse or storage: `state.findings` stays the analyst's
list, which is what the packet, the resume and the correction check all read.

These cases describe what the room does, never how it is stored: none of them names a table
or a column.
"""

from __future__ import annotations

import base64
import json
from typing import Any

import httpx
import pytest
from google_crc32c import Checksum
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRTakeKind
from app.services import internalization_room as room
from app.services.internalization_room import segments as service
from app.services.platform.storage import StoredObject
from tests.device_harness import TABLET_TEAM, a_linked_tablet
from tests.room_harness import heard_every_part, nothing_is_read_ahead, press_terminei
from tests.turn_harness import the_room_agent_is

PREFIX = "/api/internalization-room"
DEVICE = "tablet-da-equipe-1"
PASSAGE = "P01"
LANGUAGE = "pt"

#: Five stretches, so a finding can sit on frase 2 and another on frase 5 — the reading the
#: ticket's acceptance criterion is written over.
TELLINGS = (
    "As noras pediram para voltar, e por isso Noemi saiu de Moabe.",
    "Ela disse às duas noras que voltassem para a casa de suas mães.",
    "Rute disse que ia junto e não a deixaria.",
    "Orfa se despediu e voltou para o povo dela.",
    "As duas seguiram o caminho até Belém.",
)

THE_ADDITION = "o pedido das noras para voltar"
THE_MISSING = "a notícia do pão em Belém"
THE_SILENCE = "o pedido das noras, que a história guarda"


@pytest.fixture(autouse=True)
def _read_only_at_terminei(monkeypatch: pytest.MonkeyPatch) -> None:
    nothing_is_read_ahead(monkeypatch)


class ReaderOfTellings:
    """The analyst in both of its modes, and what each one was handed.

    The full reading answers with whatever the case set. The verification is **judged** on
    `resolved`: it reads the finding block line by line and decides each line against the new
    telling, so no case here can claim a retelling was accepted that never answered anything.
    What the check *raises* on the corrected stretch is the case's to set, because that is
    the input these cases are about — which finding the room raises next, and why.
    """

    def __init__(self) -> None:
        self.answer = '{"findings": []}'

    async def __call__(self, *, system_prompt: str, user_content: str, **_: Any) -> str:
        return self.answer


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


@pytest.fixture()
async def bucket(monkeypatch: pytest.MonkeyPatch) -> MemoryStore:
    from app.services.internalization_room import takes as takes_service

    store = MemoryStore()
    monkeypatch.setattr(takes_service, "_store", lambda *_, **__: store)
    return store


@pytest.fixture()
def analyst(monkeypatch: pytest.MonkeyPatch) -> ReaderOfTellings:

    reader = ReaderOfTellings()
    the_room_agent_is(monkeypatch, analyst=reader)
    return reader


@pytest.fixture(autouse=True)
def speaker(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Every system prompt the Speaker was handed, so a case can read what it was told.

    Asserted against the prompt rather than the answer: what the team hears is a generation,
    and what must never happen is the model being handed the finding the order did not pick.
    """
    handed: list[str] = []

    from app.api.internalization_room import back_translation as bt_api

    async def _speak(*, system_prompt: str, user_content: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        handed.append(system_prompt)
        return "No que vocês me traduziram, vamos olhar uma parte de novo."

    the_room_agent_is(monkeypatch, turn=_speak)

    async def _voice(text: str, *_: Any, **__: Any):
        return (type("Voiced", (), {"key": "clipe"})(), 0)

    monkeypatch.setattr(bt_api.room, "synthesize_facilitator_speech", _voice)
    return handed


@pytest.fixture()
async def client(db_session: AsyncSession, bucket: MemoryStore, monkeypatch: pytest.MonkeyPatch):
    from fastapi import FastAPI

    from app.api.internalization_room import back_translation as bt_api
    from app.api.internalization_room import router
    from app.api.internalization_room import segments as segments_api
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    said: list[str] = []

    async def _transcribe(*_: Any, **__: Any) -> str:
        return said.pop(0) if said else "algo que a equipe traduziu"

    monkeypatch.setattr(bt_api, "heard", _transcribe)
    monkeypatch.setattr(segments_api, "heard", _transcribe)

    test_app = FastAPI()
    test_app.include_router(router, prefix=PREFIX)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    tablet = await a_linked_tablet(db_session, team_id=TABLET_TEAM)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", headers=tablet.headers
    ) as c:
        c.said = said  # type: ignore[attr-defined]
        yield c


async def _open_session(client: httpx.AsyncClient) -> str:
    created = await client.post(
        f"{PREFIX}/sessions",
        json={"pericope": PASSAGE, "language": LANGUAGE},
    )
    assert created.status_code == 200, created.text
    return str(created.json()["session_id"])


async def _record(client: httpx.AsyncClient, session_id: str) -> str:
    kept = await client.post(
        f"{PREFIX}/sessions/{session_id}/takes",
        headers={"X-Room-Device": DEVICE},
        data={"kind": IRTakeKind.ENSAIO.value, "scope": PASSAGE},
        files={"file": ("tomada.m4a", b"a equipe ensaiou a passagem", "audio/mp4")},
    )
    assert kept.status_code == 200, kept.text
    return str(kept.json()["take_id"])


async def _finish(client: httpx.AsyncClient, db: AsyncSession, session_id: str) -> httpx.Response:
    """Press `terminei` with the team reporting every current part played through.

    The room refuses the check before the analyst is called while any part of the rehearsal
    is unheard, so a case about what the reading answers has to get the team past that door.
    """
    return await press_terminei(client, session_id, report=await heard_every_part(db, session_id))


async def _five_stretches_told(client: httpx.AsyncClient) -> str:
    session_id = await _open_session(client)
    take_id = await _record(client, session_id)
    client.said.extend(TELLINGS)  # type: ignore[attr-defined]
    for index in range(len(TELLINGS)):
        told = await client.post(
            f"{PREFIX}/sessions/{session_id}/back-translation/chunks",
            headers={"X-Room-Device": DEVICE},
            data={
                "take_id": take_id,
                "starts_ms": str(index * 9000),
                "ends_ms": str((index + 1) * 9000),
            },
            files={"file": ("trecho.m4a", b"um trecho traduzido", "audio/mp4")},
        )
        assert told.status_code == 200, told.text
    return session_id


async def _resumed(client: httpx.AsyncClient, session_id: str) -> dict[str, Any]:
    """What a tablet is handed when it picks the telling-back back up."""
    standing = await client.get(f"{PREFIX}/sessions/{session_id}")
    assert standing.status_code == 200, standing.text
    return dict(standing.json()["back_translation"])


async def _findings_now(db: AsyncSession, session_id: str) -> list[Any]:
    session = await room.get_session(db, session_id)
    return room.back_translation_of(session).findings


async def _the_missing_listed_before_the_addition(
    client: httpx.AsyncClient, db: AsyncSession, analyst: ReaderOfTellings
) -> tuple[str, dict[str, Any]]:
    """The reading the ticket's acceptance criterion is written over, and the turn it voiced."""
    session_id = await _five_stretches_told(client)
    analyst.answer = json.dumps(
        {
            "findings": [
                {"kind": "missing", "chunk": 2, "where": "inside", "note": THE_MISSING},
                {"kind": "addition", "chunk": 5, "note": THE_ADDITION},
            ]
        }
    )
    first = await _finish(client, db, session_id)
    assert first.status_code == 200, first.text
    return session_id, dict(first.json())


async def test_a_missing_listed_first_loses_to_an_addition(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: ReaderOfTellings, speaker
) -> None:
    """The ticket's acceptance criterion, at the seam the team actually presses.

    An addition outranks a missing element in the **Priority**, and the analyst listed the
    missing element first. Today the room raises it, the team mends frase 2, presses
    `terminei` again, and only then hears about frase 5 — which of the two they hear
    decided by the order the model happened to write its JSON in.

    Read on the turn the team first hears, which is the press that reached the analyst: the
    criterion is about that turn, and the stored verdict a second press serves is the sibling
    case's job. The Speaker is read as well as the response, because the two can disagree:
    the body names a kind and an address, and the prompt is where a note the order did not
    pick would still reach the team's ears.
    """
    session_id, voiced = await _the_missing_listed_before_the_addition(client, db_session, analyst)
    standing = await service.final_segments(db_session, session_id)

    assert voiced["finding_kind"] == "addition"
    assert voiced["finding_segment_id"] == standing[4].id
    assert THE_ADDITION in speaker[0]
    assert THE_MISSING not in speaker[0]
    assert voiced["findings_remaining"] == 2


async def test_the_replay_and_the_resume_name_the_finding_that_was_spoken(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: ReaderOfTellings
) -> None:
    """The three places that decide the pick decide it the same way.

    The fresh verdict, the stored verdict served on a second press, and the payload a tablet
    resumes on each recompute it from the stored list. Anything that ordered at one of them
    would leave a team hearing about frase 5 and looking at a screen rebuilt on frase 2.
    """
    session_id, voiced = await _the_missing_listed_before_the_addition(client, db_session, analyst)
    standing = await service.final_segments(db_session, session_id)

    replayed = (await _finish(client, db_session, session_id)).json()
    resumed = await _resumed(client, session_id)

    assert voiced["finding_kind"] == "addition"
    assert replayed["finding_kind"] == voiced["finding_kind"]
    assert replayed["finding_segment_id"] == voiced["finding_segment_id"]
    assert replayed["finding_segment_id"] == standing[4].id
    assert resumed["finding_kind"] == replayed["finding_kind"]
    assert resumed["finding_segment_id"] == replayed["finding_segment_id"]


async def test_a_filled_silence_is_raised_before_a_missing_and_still_reads_as_addition(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: ReaderOfTellings, speaker
) -> None:
    """The top tier of the **Priority**, keyed on the wire kind and kept only as a flag.

    A **Filled silence** outranks everything, and the collapse to three kinds left nothing in a
    finding to tell it from any other addition. The analyst names it with the wire kind
    `silence`; the room folds it to `addition` on arrival, so the app, the packet and the
    golden scripts see exactly what they saw before — which is precisely the cost Marcia
    refused when she refused a fourth kind.

    The packet is read as the dump of the stored findings, which is the value it copies,
    rather than by building a release: one needs a whole session behind it — comprehension,
    consent, the coverage floor, the playback report — and none of that scaffolding is what
    this case is about. What the packet could still get wrong is the dump, and this is it.
    """
    session_id = await _five_stretches_told(client)
    analyst.answer = json.dumps(
        {
            "findings": [
                {"kind": "missing", "chunk": 2, "where": "inside", "note": THE_MISSING},
                {"kind": "silence", "chunk": 1, "note": THE_SILENCE},
            ]
        }
    )
    standing_first = await _finish(client, db_session, session_id)
    assert standing_first.status_code == 200, standing_first.text
    standing = await service.final_segments(db_session, session_id)
    body = (await _finish(client, db_session, session_id)).json()
    findings = await _findings_now(db_session, session_id)
    for_the_packet = [finding.model_dump(mode="json") for finding in findings]

    assert body["finding_kind"] == "addition"
    assert body["finding_segment_id"] == standing[0].id
    assert THE_SILENCE in speaker[0]
    assert [finding.kind.value for finding in findings] == ["missing", "addition"]
    assert [finding.fills_silence for finding in findings] == [False, True]
    assert [one["kind"] for one in for_the_packet] == ["missing", "addition"]
