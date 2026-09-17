"""A told-back stretch is a thing of its own, with an address that outlives the list it was in.

Until now a stretch was a line in a JSON array on the session, and the only way to name one in
the world was its position in that array. Everything that follows from correcting *one* stretch
— which recording explains it, which slice of that recording, which version of it counts, what
it was divided out of — had nowhere to live.

These cases describe the behaviour, never the shape. None of them names a table, a column or a
field type: rename a column without changing what the room does and every one of them must stay
green.
"""

from __future__ import annotations

import base64
from typing import Any

import httpx
import pytest
from google_crc32c import Checksum
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import ValidationError
from app.db.models.internalization_room import IRPromptKey, IRSession, IRTake, IRTakeKind
from app.services.internalization_room import segments as service
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.back_translation import analyse_telling_back
from app.services.internalization_room.sessions import create_session
from app.services.internalization_room.takes import store_take
from app.services.platform.storage import StoredObject
from tests.room_harness import a_piece_still_to_be_told, heard_every_part, press_terminei

PREFIX = "/api/internalization-room"
KEY = "sala-de-teste"
DEVICE = "tablet-da-equipe-1"
ANALYST = default_prompt(IRPromptKey.BT_ANALYST)["prompt"]
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


@pytest.fixture()
async def bucket(monkeypatch: pytest.MonkeyPatch) -> MemoryStore:
    from app.services.internalization_room import takes as takes_service

    store = MemoryStore()
    monkeypatch.setattr(takes_service, "_store", lambda *_, **__: store)
    return store


@pytest.fixture()
async def client(db_session: AsyncSession, bucket: MemoryStore, monkeypatch: pytest.MonkeyPatch):
    """The room's own routes, with the transcriber and the bucket held still.

    `client.said` queues what the transcriber will answer, one entry per stretch, so a case
    can say what the team told back without a model in the loop.
    """
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


def _settings() -> Settings:
    return Settings(database_url="sqlite+aiosqlite:///./test.db", google_api_key="fake")


async def _room_session(db: AsyncSession) -> IRSession:
    return await create_session(db, pericope=PASSAGE, project_id="projeto-1")


async def _rehearsal(db: AsyncSession, session: IRSession, audio: bytes) -> IRTake:
    """One recording of the passage in the mother tongue."""
    return await store_take(
        db,
        session_id=session.id,
        device_id=DEVICE,
        project_id=session.project_id,
        pericope=session.pericope,
        kind=IRTakeKind.ENSAIO,
        scope=session.pericope,
        audio=audio,
    )


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
) -> httpx.Response:
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/back-translation/chunks",
        headers={"X-Room-Key": KEY, "X-Room-Device": DEVICE},
        data={"take_id": take_id, "starts_ms": str(starts_ms), "ends_ms": str(ends_ms)},
        files={"file": ("trecho.m4a", audio, "audio/mp4")},
    )


async def _told_so_far(client: httpx.AsyncClient, session_id: str) -> list[dict[str, Any]]:
    """What the room says the session holds, read the way the tablet reads it."""
    state = await client.get(f"{PREFIX}/sessions/{session_id}", headers={"X-Room-Key": KEY})
    assert state.status_code == 200, state.text
    return list(state.json()["back_translation"]["segments"])


# ---------------------------------------------------------------------------
# 1. A told-back stretch stays addressable afterwards
# ---------------------------------------------------------------------------


async def test_a_told_back_stretch_can_still_be_pointed_at_afterwards(
    client: httpx.AsyncClient,
) -> None:
    """After the team tells one stretch back, the room can name the recording that explains
    it and the slice inside that recording — and it can still do so once other stretches
    have been told.

    A stretch used to be findable only by counting the list it was in, so the answer to
    "which audio is this one" changed every time the list did.
    """
    session_id = await _open_session(client)
    take_id = await _record(client, session_id, b"a equipe ensaiou a passagem inteira")

    client.said.extend(["Noemi mandou Rute voltar.", "Rute disse que ia junto."])  # type: ignore[attr-defined]
    await _tell_back(
        client, session_id, take_id=take_id, starts_ms=0, ends_ms=9000, audio=b"primeiro trecho"
    )
    first = (await _told_so_far(client, session_id))[0]

    await _tell_back(
        client, session_id, take_id=take_id, starts_ms=9000, ends_ms=21000, audio=b"segundo trecho"
    )
    told = await _told_so_far(client, session_id)

    assert len(told) == 2
    assert told[0]["segment_id"] == first["segment_id"], (
        "o endereço do primeiro trecho não pode mudar porque um segundo foi contado"
    )
    assert told[0]["take_id"] == take_id
    assert (told[0]["starts_ms"], told[0]["ends_ms"]) == (0, 9000)
    assert (told[1]["starts_ms"], told[1]["ends_ms"]) == (9000, 21000)
    assert told[1]["segment_id"] != told[0]["segment_id"]


# ---------------------------------------------------------------------------
# 2. The interval is read inside the file, not across the passage
# ---------------------------------------------------------------------------


async def test_the_interval_is_read_inside_its_own_recording(
    client: httpx.AsyncClient,
) -> None:
    """A stretch that came out of the second rehearsal recording keeps times counted from
    the start of *that* recording.

    The proof is two stretches that occupy the same minute of different files: they must not
    be confused with one another, and neither may carry the other file's length added on.
    Global times over the concatenated passage are what made re-recording one stretch shift
    every stretch after it.
    """
    session_id = await _open_session(client)
    first_take = await _record(client, session_id, b"o primeiro ensaio, que a equipe abandonou")
    second_take = await _record(client, session_id, b"o segundo ensaio, que vale")

    client.said.extend(["contado do primeiro arquivo", "contado do segundo arquivo"])  # type: ignore[attr-defined]
    await _tell_back(
        client, session_id, take_id=first_take, starts_ms=60000, ends_ms=90000, audio=b"trecho A"
    )
    await _tell_back(
        client, session_id, take_id=second_take, starts_ms=60000, ends_ms=90000, audio=b"trecho B"
    )

    told = await _told_so_far(client, session_id)

    assert [one["take_id"] for one in told] == [first_take, second_take], (
        "cada trecho aponta para o arquivo de onde saiu"
    )
    assert [(one["starts_ms"], one["ends_ms"]) for one in told] == [
        (60000, 90000),
        (60000, 90000),
    ], "o mesmo minuto de dois arquivos é o mesmo par de números, e não se confunde"
    assert told[0]["segment_id"] != told[1]["segment_id"]


# ---------------------------------------------------------------------------
# 3. The order the team told in survives
# ---------------------------------------------------------------------------


async def test_the_order_the_team_told_in_survives_a_later_write(
    db_session: AsyncSession, bucket: MemoryStore
) -> None:
    """Reading the session gives the stretches back in the order they were told.

    The middle stretch is replaced, so its current version is the **last** row written and
    must still read **second**. That is what separates a real ordering from the order rows
    happened to land in — and it holds whatever identifier each stretch was given.
    """
    session = await _room_session(db_session)
    take = await _rehearsal(db_session, session, b"o ensaio")

    first = await service.capture_segment(
        db_session, session, take_id=take.id, starts_ms=0, ends_ms=9000, transcript="primeiro"
    )
    middle = await service.capture_segment(
        db_session, session, take_id=take.id, starts_ms=9000, ends_ms=21000, transcript="segundo"
    )
    last = await service.capture_segment(
        db_session, session, take_id=take.id, starts_ms=21000, ends_ms=30000, transcript="terceiro"
    )
    again = await service.capture_segment(
        db_session,
        session,
        take_id=take.id,
        starts_ms=9000,
        ends_ms=21000,
        bridge_take_id="retro-de-novo",
        transcript="segundo, contado outra vez",
        replaces=middle,
    )

    told = await service.final_segments(db_session, session.id)

    assert [one.id for one in told] == [first.id, again.id, last.id], (
        "a ordem é a que a equipe contou, e não a ordem em que as linhas foram escritas"
    )


# ---------------------------------------------------------------------------
# 4. A new version retires the old one without erasing it
# ---------------------------------------------------------------------------


async def test_a_new_version_retires_the_previous_one_without_erasing_it(
    db_session: AsyncSession, bucket: MemoryStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With two versions for one position, the analyst reads the one that counts.

    The earlier one stays recoverable, marked as replaced, and never comes back into the
    reading by accident — which is the failure that matters, because what the analyst reads
    is what the team is told to fix.
    """
    import sys

    session = await _room_session(db_session)
    take = await _rehearsal(db_session, session, b"o ensaio")

    stale = await service.capture_segment(
        db_session,
        session,
        take_id=take.id,
        starts_ms=0,
        ends_ms=9000,
        transcript="a explicação velha",
    )
    fresh = await service.capture_segment(
        db_session,
        session,
        take_id=take.id,
        starts_ms=0,
        ends_ms=9000,
        transcript="a explicação nova",
        replaces=stale,
    )

    seen: dict[str, str] = {}

    async def agent(*, system_prompt: str, user_content: str, **_: Any) -> str:
        seen["prompt"] = system_prompt
        return '{"evidence_sufficient": true, "findings": []}'

    monkeypatch.setattr(
        sys.modules["app.services.internalization_room.back_translation"], "call_agent", agent
    )
    await analyse_telling_back(
        segments=await service.final_segments(db_session, session.id),
        scope=PASSAGE,
        pericope_num=PASSAGE,
        analyst_prompt=ANALYST,
        settings=_settings(),
    )

    assert "a explicação nova" in seen["prompt"]
    assert "a explicação velha" not in seen["prompt"], (
        "a versão aposentada não volta a ser lida pelo analista"
    )
    retired = await service.retired_segments(db_session, session.id)
    assert [one.id for one in retired] == [stale.id], "a anterior continua recuperável"
    assert (await service.segment_by_id(db_session, stale.id)).id == stale.id
    assert [one.id for one in await service.final_segments(db_session, session.id)] == [fresh.id]


# ---------------------------------------------------------------------------
# 5. A stretch knows what it was divided out of
# ---------------------------------------------------------------------------


async def test_a_stretch_knows_which_stretch_it_was_divided_out_of(
    db_session: AsyncSession, bucket: MemoryStore
) -> None:
    """Given a stretch born of another, the room can say which one is the parent — and the
    parent stops counting as a final unit in favour of its children.

    The verb that performs the division belongs to another slice; this exercises the relation
    through the service that writes it.
    """
    session = await _room_session(db_session)
    take = await _rehearsal(db_session, session, b"o ensaio")

    whole = await service.capture_segment(
        db_session, session, take_id=take.id, starts_ms=0, ends_ms=20000, transcript="o todo"
    )
    head = await service.capture_segment(
        db_session,
        session,
        take_id=take.id,
        starts_ms=0,
        ends_ms=8000,
        transcript="a primeira metade",
        parent=whole,
    )
    tail = await service.capture_segment(
        db_session,
        session,
        take_id=take.id,
        starts_ms=8000,
        ends_ms=20000,
        transcript="a segunda metade",
        parent=whole,
    )

    assert (await service.parent_of(db_session, head)).id == whole.id  # type: ignore[union-attr]
    assert (await service.parent_of(db_session, tail)).id == whole.id  # type: ignore[union-attr]
    assert await service.parent_of(db_session, whole) is None

    final = await service.final_segments(db_session, session.id)

    assert [one.id for one in final] == [head.id, tail.id], (
        "o pai deixa de valer como unidade final em favor dos filhos"
    )


# ---------------------------------------------------------------------------
# 7. Today's back translation goes on working
# ---------------------------------------------------------------------------


async def test_the_back_translation_the_room_already_does_goes_on_working(
    client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The regression case of the slice, and it is large on purpose.

    Record the passage, tell it back in pieces, ask for the verdict, receive the findings —
    each step answering as it answers today, including the finding landing on one named
    stretch rather than on the whole passage.
    """
    import json
    import sys

    turn_module = sys.modules["app.services.internalization_room.run_turn"]

    session_id = await _open_session(client)
    take_id = await _record(client, session_id, b"a equipe ensaiou a passagem inteira")

    client.said.extend(["Noemi mandou Rute voltar.", "Rute disse que ia junto."])  # type: ignore[attr-defined]
    first = await _tell_back(
        client, session_id, take_id=take_id, starts_ms=0, ends_ms=9000, audio=b"primeiro trecho"
    )
    second = await _tell_back(
        client, session_id, take_id=take_id, starts_ms=9000, ends_ms=21000, audio=b"segundo trecho"
    )

    assert first.status_code == 200 and first.json()["captured"] is True
    assert second.json()["chunks"] == 2

    async def analyst(*, system_prompt: str, user_content: str, **_: Any) -> str:
        return (
            '{"evidence_sufficient": true, "findings": ['
            '{"kind": "missing", "chunk": 2, "note": "faltou dizer para onde Rute ia"}]}'
        )

    monkeypatch.setattr(
        sys.modules["app.services.internalization_room.back_translation"], "call_agent", analyst
    )

    async def speaker(*, system_prompt: str, user_content: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return "Vocês contaram bem. Falta uma coisa."

    monkeypatch.setattr(turn_module, "call_agent", speaker)

    async def _voice(*_: Any, **__: Any):
        return (type("Voiced", (), {"key": "uma-chave"})(), 0)

    monkeypatch.setattr(
        sys.modules["app.api.internalization_room.back_translation"].room,
        "synthesize_facilitator_speech",
        _voice,
    )

    verdict = await press_terminei(
        client, session_id, report=await heard_every_part(db_session, session_id)
    )

    assert verdict.status_code == 200, verdict.text
    body = verdict.json()
    assert body["checked"] is False
    assert body["finding_kind"] == "missing"
    assert body["findings_remaining"] == 1

    told = await _told_so_far(client, session_id)
    assert body["finding_segment_id"] == told[1]["segment_id"], (
        "o achado aponta o trecho que o analista numerou, e não a passagem inteira"
    )

    restarted = await client.post(
        f"{PREFIX}/sessions/{session_id}/back-translation/restart", headers={"X-Room-Key": KEY}
    )

    assert restarted.status_code == 200, restarted.text
    assert restarted.json()["chunks"] == 0
    assert await _told_so_far(client, session_id) == [], (
        "recomeçar a retrotradução deixa a sessão sem trecho corrente nenhum"
    )


# ---------------------------------------------------------------------------
# Raised in review: two states the service could reach and did not handle
# ---------------------------------------------------------------------------


async def test_a_stretch_that_was_divided_cannot_be_replaced_as_a_unit(
    db_session: AsyncSession, bucket: MemoryStore
) -> None:
    """Replacing a divided stretch left its children pointing at a retired parent.

    The walk starts at the roots, so those children sat under an id nothing reached and fell
    out of the reading with nothing saying so — the team's work, gone from what the analyst
    sees and from what the tablet resumes.

    Refused, because the parent stopped being a unit the moment it was divided: what would be
    re-recorded is the children, one at a time. F6 and F7 can give that a verb; they cannot be
    handed a service that drops rows in the meantime.
    """
    session = await _room_session(db_session)
    take = await _rehearsal(db_session, session, b"o ensaio")

    whole = await service.capture_segment(
        db_session, session, take_id=take.id, starts_ms=0, ends_ms=20000, transcript="o todo"
    )
    head = await service.capture_segment(
        db_session, session, take_id=take.id, starts_ms=0, ends_ms=8000, parent=whole
    )

    with pytest.raises(ValidationError):
        await service.capture_segment(
            db_session, session, take_id=take.id, starts_ms=0, ends_ms=20000, replaces=whole
        )

    assert [one.id for one in await service.final_segments(db_session, session.id)] == [head.id]


async def test_a_piece_cut_off_and_not_yet_told_is_not_read_as_something_told(
    db_session: AsyncSession, bucket: MemoryStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A piece the team cut has nothing told back about it yet, and nothing is not a text.

    It reached the analyst as a literal ``None`` — a line the team never said, which the
    analyst compares against the map and can raise a finding on. The piece is real and the
    tablet must still see it; what it has no business being is evidence.

    Cutting is the one verb left that leaves a stretch standing with nothing said on it, so the
    rule is measured over that: the counts below are what a cut produces, and what carries the
    rule is that the untold piece is absent from what the analyst reads.
    """
    import sys

    session = await _room_session(db_session)
    take = await _rehearsal(db_session, session, b"o ensaio")

    kept = await service.capture_segment(
        db_session,
        session,
        take_id=take.id,
        starts_ms=0,
        ends_ms=9000,
        transcript="Noemi mandou Rute voltar.",
    )
    whole = await service.capture_segment(
        db_session, session, take_id=take.id, starts_ms=9000, ends_ms=21000, transcript="a refazer"
    )
    waiting = await a_piece_still_to_be_told(db_session, session, whole)

    current = await service.final_segments(db_session, session.id)
    readable = service.told_back(current)

    assert len(current) == 3, "a peça por contar continua sendo uma unidade para o tablet"
    assert len(readable) == 2
    assert waiting.id not in [one.id for one in readable], (
        "o que a equipe ainda não contou não é o que o analista lê"
    )
    assert kept.id in [one.id for one in readable]

    seen: dict[str, str] = {}

    async def agent(*, system_prompt: str, user_content: str, **_: Any) -> str:
        seen["prompt"] = system_prompt
        return (
            '{"evidence_sufficient": true, "findings": '
            '[{"kind": "missing", "chunk": 3, "note": "x"}]}'
        )

    monkeypatch.setattr(
        sys.modules["app.services.internalization_room.back_translation"], "call_agent", agent
    )
    analysis = await analyse_telling_back(
        segments=readable,
        scope=PASSAGE,
        pericope_num=PASSAGE,
        analyst_prompt=ANALYST,
        settings=_settings(),
    )

    assert "None" not in seen["prompt"].split("## The telling-back")[-1], (
        "o analista não pode ler um 'None' como se a equipe tivesse dito isso"
    )
    assert analysis is not None
    assert analysis.findings[0].segment_id is None, (
        "e o achado na posição onde a peça por contar estaria não cai nela: ela não foi lida"
    )
