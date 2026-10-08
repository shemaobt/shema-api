"""An addition and a missing element on the same frase are one thing, all the way through.

A telling that swaps one relation for another puts something in and drops what the story
tells in its place. The analyst sees two findings on one frase; the team made one mistake.
Raised one at a time, the room asks them to record that part again for the addition and,
the round after, to record the same part again for the missing element — a second
re-recording of the same scene, for one swap.

So the pair travels as one: one thing said to the team, one fix asked for, one verification
of the retelling, and both findings cleared by it. It is keyed on the frase the analyst
numbered rather than on the stretch each half resolved to, because a missing element placed
*after* frase 1 sits at the start of stretch 2 (ADR 0007) and a rule comparing stretches
would never see the swap.

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

from app.db.models.internalization_room import IRSegment, IRTakeKind
from app.services import internalization_room as room
from app.services.internalization_room import segments as service
from app.services.platform.storage import StoredObject
from tests.room_harness import heard_every_part, nothing_is_read_ahead, press_terminei
from tests.turn_harness import the_room_agent_is

PREFIX = "/api/internalization-room"
KEY = "sala-de-teste"
DEVICE = "tablet-da-equipe-1"
PASSAGE = "P01"
LANGUAGE = "pt"

#: The swap, as the team told it: a cause that is theirs, and the news of the bread gone.
FIRST_TELLING = "As noras pediram para voltar, e por isso Noemi saiu de Moabe."
SECOND_TELLING = "Ela disse às duas noras que voltassem para a casa de suas mães."
THIRD_TELLING = "Rute disse que ia junto e não a deixaria."

#: The two halves of that one swap, in the analyst's words.
THE_ADDITION = "o pedido das noras para voltar"
THE_MISSING = "a notícia do pão em Belém"

#: The retelling that answers neither: the news arrived and the cause stayed.
THE_CAUSE_STILL_THERE = "As noras pediram para voltar, e Noemi soube da notícia do pão em Belém."


@pytest.fixture(autouse=True)
def _read_only_at_terminei(monkeypatch: pytest.MonkeyPatch) -> None:
    nothing_is_read_ahead(monkeypatch)


class ReaderOfTellings:
    """The analyst, in both of its modes, and what each one was handed.

    The full reading answers with whatever the case set. The verification is **judged**, not
    dictated: it reads the finding block line by line and decides each line against the new
    telling — an addition is answered when what the team put in is no longer said, a missing
    element when what the story tells is said. A double that echoed a verdict back would
    leave every case here proving nothing about the block it was handed.
    """

    def __init__(self) -> None:
        self.full_readings: list[str] = []
        self.answer = '{"findings": []}'

    async def __call__(self, *, system_prompt: str, user_content: str, **_: Any) -> str:
        self.full_readings.append(system_prompt)
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
    and what must never happen is the model being handed one half of a swap.
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
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    monkeypatch.setattr(get_settings(), "internalization_room_api_key", KEY, raising=False)

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


async def _record(client: httpx.AsyncClient, session_id: str) -> str:
    kept = await client.post(
        f"{PREFIX}/sessions/{session_id}/takes",
        headers={"X-Room-Key": KEY, "X-Room-Device": DEVICE},
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


async def _three_stretches_told(client: httpx.AsyncClient) -> str:
    session_id = await _open_session(client)
    take_id = await _record(client, session_id)
    client.said.extend([FIRST_TELLING, SECOND_TELLING, THIRD_TELLING])  # type: ignore[attr-defined]
    for index in range(3):
        told = await client.post(
            f"{PREFIX}/sessions/{session_id}/back-translation/chunks",
            headers={"X-Room-Key": KEY, "X-Room-Device": DEVICE},
            data={
                "take_id": take_id,
                "starts_ms": str(index * 9000),
                "ends_ms": str((index + 1) * 9000),
            },
            files={"file": ("trecho.m4a", b"um trecho traduzido", "audio/mp4")},
        )
        assert told.status_code == 200, told.text
    return session_id


async def _tell_that_stretch_again(
    client: httpx.AsyncClient, session_id: str, segment: IRSegment, *, saying: str
) -> None:
    """The team answers the finding by telling that one stretch back again, over the audio."""
    client.said.append(saying)  # type: ignore[attr-defined]
    answered = await client.post(
        f"{PREFIX}/sessions/{session_id}/segments/{segment.id}/replace",
        headers={"X-Room-Key": KEY, "X-Room-Device": DEVICE},
        data={
            "take_id": segment.take_id,
            "starts_ms": str(segment.starts_ms),
            "ends_ms": str(segment.ends_ms),
        },
        files={"file": ("de-novo.m4a", b"traduzido de novo", "audio/mp4")},
    )
    assert answered.status_code == 200, answered.text


def _the_pair_on_the_first_frase(where: str = "inside") -> str:
    return json.dumps(
        {
            "findings": [
                {"kind": "addition", "chunk": 1, "note": THE_ADDITION},
                {"kind": "missing", "chunk": 1, "where": where, "note": THE_MISSING},
            ]
        }
    )


async def _the_swap_raised(
    client: httpx.AsyncClient, db: AsyncSession, analyst: ReaderOfTellings, *, where: str = "inside"
) -> tuple[str, IRSegment]:
    """The room reads the whole telling-back once and raises the swap on frase 1."""
    session_id = await _three_stretches_told(client)
    analyst.answer = _the_pair_on_the_first_frase(where)
    first = await _finish(client, db, session_id)
    assert first.status_code == 200, first.text
    assert analyst.full_readings, "a primeira leitura tem de ter acontecido"
    standing = await service.final_segments(db, session_id)
    return session_id, standing[0]


async def _resumed(client: httpx.AsyncClient, session_id: str) -> dict[str, Any]:
    """What a tablet is handed when it picks the telling-back back up."""
    standing = await client.get(f"{PREFIX}/sessions/{session_id}", headers={"X-Room-Key": KEY})
    assert standing.status_code == 200, standing.text
    return dict(standing.json()["back_translation"])


async def _findings_now(db: AsyncSession, session_id: str) -> list[Any]:
    session = await room.get_session(db, session_id)
    return room.back_translation_of(session).findings


async def test_the_swap_reaches_the_team_as_one_thing(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: ReaderOfTellings, speaker
) -> None:
    """Acceptance 1, at the seam the team actually presses.

    Both halves in front of the Speaker, the addition first, and one thing left to act on:
    the count is what tells the team how much of the round is still ahead of them.

    Two presses on purpose, because the count is served from two places. The prompt read here
    is the first press, which reached the analyst and voiced a verdict; the body is the second,
    which decides nothing new and serves the verdict it stored. Both had to learn that a swap
    is one thing, and a case that pressed once would have watched only one of them.
    """
    session_id, _ = await _the_swap_raised(client, db_session, analyst)
    body = (await _finish(client, db_session, session_id)).json()

    assert THE_ADDITION in speaker[0]
    assert THE_MISSING in speaker[0]
    assert speaker[0].index(THE_ADDITION) < speaker[0].index(THE_MISSING)
    assert body["findings_remaining"] == 1
    assert body["finding_kind"] == "addition"


async def test_an_unresolved_pair_stays_on_the_corrected_stretch(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: ReaderOfTellings
) -> None:
    """Acceptance 4, the other half. Half-answered is not answered.

    The news of the bread arrived and the cause the team put in is still there, so the swap
    is still a swap. Both halves stay, and both move to the stretch that now counts: left on
    the row they were raised on, they would send the team to a telling that no longer exists.
    """
    session_id, first = await _the_swap_raised(client, db_session, analyst)

    await _tell_that_stretch_again(client, session_id, first, saying=THE_CAUSE_STILL_THERE)
    answered = await _finish(client, db_session, session_id)
    standing = await service.final_segments(db_session, session_id)
    findings = await _findings_now(db_session, session_id)

    assert answered.json()["findings_remaining"] == 1
    assert [finding.kind.value for finding in findings] == ["addition", "missing"]
    assert {finding.segment_id for finding in findings} == {standing[0].id}
    assert {finding.chunk for finding in findings} == {1}


async def test_a_missing_placed_after_the_frase_is_still_the_same_swap(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: ReaderOfTellings, speaker
) -> None:
    """Acceptance 2, at the seam. The two halves land on two stretches and are one thing.

    *After* frase 1 resolves to stretch 2, so the missing element's address is not the
    addition's. The frase number is what holds them together, and the stretch the team is
    sent to is the addition's — the part where the swap happened.
    """
    session_id, first = await _the_swap_raised(client, db_session, analyst, where="after")
    body = (await _finish(client, db_session, session_id)).json()

    assert THE_ADDITION in speaker[0]
    assert THE_MISSING in speaker[0]
    assert body["findings_remaining"] == 1
    assert body["finding_segment_id"] == first.id


async def test_a_resumed_tablet_is_sent_to_the_stretch_of_the_swap(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: ReaderOfTellings
) -> None:
    """What the screen rebuilds after a restart is the stretch the verdict named.

    The analyst listed the missing element first and it is placed after frase 1, so the half
    at the front of the list points at stretch 2. A resume reading it would rebuild the screen
    on the stretch after the swap, and the team would record the wrong part — the turn they
    just heard named the other one.
    """
    session_id = await _three_stretches_told(client)
    analyst.answer = json.dumps(
        {
            "findings": [
                {"kind": "missing", "chunk": 1, "where": "after", "note": THE_MISSING},
                {"kind": "addition", "chunk": 1, "note": THE_ADDITION},
            ]
        }
    )
    voiced = (await _finish(client, db_session, session_id)).json()
    standing = await service.final_segments(db_session, session_id)

    resumed = await _resumed(client, session_id)

    assert resumed["finding_kind"] == "addition"
    assert resumed["finding_segment_id"] == standing[0].id
    assert resumed["finding_segment_id"] == voiced["finding_segment_id"]
