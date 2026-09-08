"""A mend is checked by counting what the stretch carried, not by asking what is missing.

The verification of a correction already compares one retold stretch against the version it
replaced. What it could not do reliably is notice a *loss*: the team answers the finding they
were given, and in retelling the whole stretch they quietly drop something only that stretch
carried. Asked holistically — "did answering it break anything?" — a reader confirms what is
present far better than it notices what is absent, and the absence goes unreported.

So the question is asked the other way round. The verification first **enumerates** what the
earlier telling of this stretch carried, and marks each one as still told or not. An element
marked as no longer told **is** a loss on this stretch, derived here rather than waited for:
the room does not depend on the reader also volunteering it under `findings`. The loss is then
caught in the stretch it fell out of, in the same turn, instead of surfacing turns later in a
whole reading that can only guess which stretch it belonged to.

These cases are about what the room does with the reply, so the reader is a double that returns
the reply each case sets, verbatim. What it says is the case's input; what the team is asked
next is the case's subject. None of them names a table or a column.
"""

from __future__ import annotations

import base64
import importlib
import json
import logging
import re
from typing import Any

import httpx
import pytest
from google_crc32c import Checksum
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSegment, IRTakeKind
from app.services.internalization_room import segments as service
from app.services.platform.storage import StoredObject

PREFIX = "/api/internalization-room"
KEY = "sala-de-teste"
DEVICE = "tablet-da-equipe-1"
PASSAGE = "P01"
#: Named rather than defaulted: the room's floor is English and every telling here is
#: Portuguese, so a session left on the floor would meet the bridge-language gate.
LANGUAGE = "pt"

#: The heading only the correction prompt carries. The double tells the two readings apart by
#: it, the way a reader would — not by counting calls.
CORRECTION_MARK = "## What the team told back now"

#: Where the room's own logger writes when it cannot read part of a reply.
ROOM_LOG = "app.services.internalization_room.back_translation"

FIRST_TELLING = "Noemi ouviu que havia pão em Belém e resolveu voltar de Moabe."
SECOND_TELLING = "Ela disse às duas noras que voltassem para a casa de suas mães."
THIRD_TELLING = "Rute disse que ia junto e não a deixaria."

#: The correction under test throughout: it answers the finding — Orpah is named now — and in
#: retelling the whole stretch it drops the bread, which only this stretch carried. This is the
#: shape measured in the room on 2026-09-02, where a stretch retold to answer one finding came
#: back without a clause nobody asked about.
ANSWERED_AND_LOST = "Noemi e Orfa voltaram de Moabe para Belém."

STILL_TOLD = "Noemi voltou de Moabe"
NO_LONGER_TOLD = "havia pão em Belém"
#: The element the finding on the first stretch names as missing — "Orfa não apareceu neste
#: trecho." A correction that brings it back is the answer arriving, never an addition.
BROUGHT_BACK = "Orfa é citada pelo nome"


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


class ReaderOfTellings:
    """The analyst in both of its modes, answering with whatever the case set.

    Unlike the double in `test_ir_a_correction_is_verified_on_its_own`, this one does not judge:
    every case here is about what the room derives from a reply, so the reply is the input and
    dictating it is the point. A double that decided for itself could not be made to enumerate
    an element as lost and stay silent under `findings`, which is the whole first case.
    """

    def __init__(self) -> None:
        self.full_readings: list[str] = []
        self.verifications: list[str] = []
        self.answer = '{"evidence_sufficient": true, "findings": []}'
        self.verification = json.dumps({"resolved": True, "findings": []})

    async def __call__(self, *, system_prompt: str, user_content: str, **_: Any) -> str:
        if CORRECTION_MARK in system_prompt:
            self.verifications.append(system_prompt)
            return self.verification
        self.full_readings.append(system_prompt)
        return self.answer


def _a_reply_enumerating(
    carried: Any,
    *,
    resolved: bool = True,
    findings: list[dict[str, str]] | None = None,
    brought_back: Any = None,
) -> str:
    """A verification reply that counts what the earlier telling carried before judging."""
    body: dict[str, Any] = {"carried": carried, "resolved": resolved, "findings": findings or []}
    if brought_back is not None:
        body["brought_back"] = brought_back
    return json.dumps(body)


def _element(text: str, *, still_told: bool) -> dict[str, Any]:
    return {"element": text, "still_told": still_told}


@pytest.fixture()
async def bucket(monkeypatch: pytest.MonkeyPatch) -> MemoryStore:
    from app.services.internalization_room import takes as takes_service

    store = MemoryStore()
    monkeypatch.setattr(takes_service, "_store", lambda *_, **__: store)
    return store


@pytest.fixture()
def analyst(monkeypatch: pytest.MonkeyPatch) -> ReaderOfTellings:
    from app.services.internalization_room import back_translation as bt_service

    reader = ReaderOfTellings()
    monkeypatch.setattr(bt_service, "call_agent", reader)
    return reader


@pytest.fixture(autouse=True)
def spoken(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """What the room hands the Speaker, so a case can read the finding the team is told about.

    The note never reaches the response body — the team hears it spoken. What the room sends
    the Speaker about this finding is the nearest thing to that a case can hold, and it is the
    same text either way.
    """
    briefed: list[str] = []

    from app.api.internalization_room import back_translation as bt_api

    turn_module = importlib.import_module("app.services.internalization_room.run_turn")

    async def speaker(*, system_prompt: str, user_content: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        briefed.append(system_prompt)
        return "No que você me contou, vamos olhar uma parte de novo."

    monkeypatch.setattr(turn_module, "call_agent", speaker)

    async def _voice(text: str, *_: Any, **__: Any):
        return (type("Voiced", (), {"key": "clipe"})(), 0)

    monkeypatch.setattr(bt_api.room, "synthesize_facilitator_speech", _voice)
    return briefed


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
        return said.pop(0) if said else "algo que a equipe contou"

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


async def _tell_back(
    client: httpx.AsyncClient, session_id: str, *, take_id: str, starts_ms: int, ends_ms: int
) -> None:
    told = await client.post(
        f"{PREFIX}/sessions/{session_id}/back-translation/chunks",
        headers={"X-Room-Key": KEY, "X-Room-Device": DEVICE},
        data={"take_id": take_id, "starts_ms": str(starts_ms), "ends_ms": str(ends_ms)},
        files={"file": ("trecho.m4a", b"um trecho contado", "audio/mp4")},
    )
    assert told.status_code == 200, told.text


async def _finish(client: httpx.AsyncClient, session_id: str) -> httpx.Response:
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/back-translation/finish", headers={"X-Room-Key": KEY}
    )


async def _tell_that_stretch_again(
    client: httpx.AsyncClient, session_id: str, segment: IRSegment, *, saying: str
) -> None:
    """The team answers a finding by telling that one stretch back again, over the same audio."""
    client.said.append(saying)  # type: ignore[attr-defined]
    answered = await client.post(
        f"{PREFIX}/sessions/{session_id}/segments/{segment.id}/replace",
        headers={"X-Room-Key": KEY, "X-Room-Device": DEVICE},
        data={
            "take_id": segment.take_id,
            "starts_ms": str(segment.starts_ms),
            "ends_ms": str(segment.ends_ms),
        },
        files={"file": ("de-novo.m4a", b"contado de novo", "audio/mp4")},
    )
    assert answered.status_code == 200, answered.text


async def _a_finding_raised_on_the_first_stretch(
    client: httpx.AsyncClient, db: AsyncSession, analyst: ReaderOfTellings
) -> tuple[str, IRSegment]:
    """The room reads the whole telling-back once and raises one finding on stretch one."""
    session_id = await _open_session(client)
    take_id = await _record(client, session_id)
    client.said.extend([FIRST_TELLING, SECOND_TELLING, THIRD_TELLING])  # type: ignore[attr-defined]
    for index in range(3):
        await _tell_back(
            client, session_id, take_id=take_id, starts_ms=index * 9000, ends_ms=(index + 1) * 9000
        )
    analyst.answer = json.dumps(
        {
            "evidence_sufficient": True,
            "findings": [
                {"kind": "missing", "chunk": 1, "note": "Orfa não apareceu neste trecho."}
            ],
        }
    )
    first = await _finish(client, session_id)
    assert first.status_code == 200, first.text
    assert analyst.full_readings, "a primeira leitura tem de ter acontecido"
    standing = await service.final_segments(db, session_id)
    return session_id, standing[0]


async def _a_correction_verified_as(
    client: httpx.AsyncClient,
    db: AsyncSession,
    analyst: ReaderOfTellings,
    reply: str,
    *,
    saying: str = ANSWERED_AND_LOST,
) -> tuple[dict[str, Any], IRSegment]:
    """One stretch retold to answer the finding, verified with the reply the case dictates.

    The closing reading is told to find nothing: what is under test is what the verification
    made of this stretch, never what a whole reading makes of the passage afterwards.
    """
    session_id, first = await _a_finding_raised_on_the_first_stretch(client, db, analyst)
    await _tell_that_stretch_again(client, session_id, first, saying=saying)
    analyst.verification = reply
    analyst.answer = '{"evidence_sufficient": true, "findings": []}'

    answered = await _finish(client, session_id)
    assert answered.status_code == 200, answered.text
    assert analyst.verifications, "a correção tem de ter sido verificada, não relida"
    corrected = (await service.final_segments(db, session_id))[0]
    return answered.json(), corrected


@pytest.mark.asyncio
async def test_an_element_counted_as_no_longer_told_is_a_finding_on_that_stretch(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: ReaderOfTellings
) -> None:
    """The case the slice exists for: the count says it fell, so the room says it fell.

    The reader answered the finding, enumerated the bread as no longer told, and volunteered
    nothing under `findings` — which is exactly how the loss escaped in the room. The room does
    not wait to be told twice: an element counted as no longer told is a loss on this stretch.
    """
    body, corrected = await _a_correction_verified_as(
        client,
        db_session,
        analyst,
        _a_reply_enumerating(
            [_element(STILL_TOLD, still_told=True), _element(NO_LONGER_TOLD, still_told=False)],
            resolved=True,
            findings=[],
        ),
    )

    assert body["findings_remaining"] == 1
    assert body["finding_kind"] == "missing"
    assert body["finding_segment_id"] == corrected.id, (
        "a perda tem de ficar pendurada no trecho de onde caiu; foi o endereço ambíguo da "
        "releitura completa que fez o mesmo conteúdo ser dito em dois trechos"
    )
    assert body["checked"] is False


@pytest.mark.asyncio
async def test_the_team_is_told_which_element_fell(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: ReaderOfTellings,
    spoken: list[str],
) -> None:
    """A loss the team cannot name is one they cannot mend."""
    await _a_correction_verified_as(
        client,
        db_session,
        analyst,
        _a_reply_enumerating(
            [_element(STILL_TOLD, still_told=True), _element(NO_LONGER_TOLD, still_told=False)]
        ),
    )

    about = _the_finding_the_speaker_was_given(spoken)
    assert NO_LONGER_TOLD in about, (
        f"o achado derivado tem de nomear o elemento perdido; a sala mandou dizer: {about!r}"
    )
    assert STILL_TOLD not in about, "o que continua dito não é uma perda"


_FINDING_LINE = re.compile(
    r"^- (?:missing|addition|meaning_change|preservation_violation|unclear): (.+)$", re.M
)


def _the_finding_the_speaker_was_given(spoken: list[str]) -> str:
    """The finding as the room handed it to the Speaker on the last turn it took.

    The note never reaches the response body — the team hears it spoken — so this is the
    nearest a case can get to what they are actually told, and it is the same text.
    """
    assert spoken, "a sala tinha de ter falado alguma coisa"
    found = _FINDING_LINE.findall(spoken[-1])
    assert found, f"nenhum achado chegou ao falante neste turno: {spoken[-1][-400:]!r}"
    return "\n".join(found)


@pytest.mark.asyncio
async def test_a_count_with_nothing_lost_and_nothing_reported_is_a_clean_mend(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: ReaderOfTellings
) -> None:
    """The guard: enumerating is not a way of manufacturing findings.

    Without this, a room that raised a loss on every correction would pass the case above and
    trap the team re-recording a stretch that was already right.
    """
    body, _ = await _a_correction_verified_as(
        client,
        db_session,
        analyst,
        _a_reply_enumerating(
            [_element(STILL_TOLD, still_told=True), _element(NO_LONGER_TOLD, still_told=True)]
        ),
        saying="Noemi e Orfa voltaram de Moabe para Belém, onde havia pão.",
    )

    assert body["findings_remaining"] == 0
    assert body["finding_kind"] is None


@pytest.mark.asyncio
async def test_an_element_both_counted_and_reported_is_heard_once(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: ReaderOfTellings
) -> None:
    """One loss is one thing to mend, however many times the reader said it.

    A reader that both enumerates the bread as no longer told and reports it under `findings`
    is describing one loss. Counting it twice would ask the team about the same clause on this
    turn and again on the next, which is how a room stops being followable.
    """
    body, corrected = await _a_correction_verified_as(
        client,
        db_session,
        analyst,
        _a_reply_enumerating(
            [_element(STILL_TOLD, still_told=True), _element(NO_LONGER_TOLD, still_told=False)],
            findings=[
                {
                    "kind": "missing",
                    "note": f"A nova contagem não diz mais que {NO_LONGER_TOLD}.",
                }
            ],
        ),
    )

    assert body["findings_remaining"] == 1
    assert body["finding_kind"] == "missing"
    assert body["finding_segment_id"] == corrected.id


@pytest.mark.asyncio
async def test_counting_does_not_turn_another_kind_of_finding_into_a_loss(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: ReaderOfTellings
) -> None:
    """The guard on the derivation's reach: it decides losses, and nothing else.

    Everything the earlier telling carried is still told, and what the reader raises is a
    changed meaning. A derivation that read the enumeration as evidence about anything but
    presence would answer the team about a loss that did not happen.
    """
    body, _ = await _a_correction_verified_as(
        client,
        db_session,
        analyst,
        _a_reply_enumerating(
            [_element(STILL_TOLD, still_told=True), _element(NO_LONGER_TOLD, still_told=True)],
            findings=[{"kind": "meaning_change", "note": "A nova contagem diz que ela insistiu."}],
        ),
    )

    assert body["findings_remaining"] == 1
    assert body["finding_kind"] == "meaning_change"


@pytest.mark.asyncio
async def test_an_element_the_map_gives_that_only_the_new_telling_states_is_a_clean_mend(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: ReaderOfTellings
) -> None:
    """The mirror of a loss: an element arriving is the correction, not a fresh finding.

    Nothing the earlier telling carried is lost, and the new telling also states an element the
    map gives that the earlier telling never had — exactly what answering a finding that named a
    missing element looks like. Enumerated under `brought_back`, with `findings` left empty, this
    has to read as a clean mend, not a loss to chase or an addition to refuse.
    """
    body, _ = await _a_correction_verified_as(
        client,
        db_session,
        analyst,
        _a_reply_enumerating(
            [
                _element(STILL_TOLD, still_told=True),
                _element(NO_LONGER_TOLD, still_told=True),
            ],
            findings=[],
            brought_back=[BROUGHT_BACK],
        ),
        saying="Noemi e Orfa voltaram de Moabe para Belém, onde havia pão.",
    )

    assert body["findings_remaining"] == 0
    assert body["finding_kind"] is None


@pytest.mark.asyncio
async def test_an_addition_matching_what_was_brought_back_is_suppressed(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: ReaderOfTellings
) -> None:
    """The mechanical belt: a reader that slips and reports the correction as an addition anyway.

    The prompt's own `Added` rule already says an element the map gives is never an addition, but
    a model can still get there — this is the backstop for that slip, mirroring the dedupe
    `_already_reported` already does for a loss the reader both counted and wrote out.
    """
    body, _ = await _a_correction_verified_as(
        client,
        db_session,
        analyst,
        _a_reply_enumerating(
            [_element(STILL_TOLD, still_told=True), _element(NO_LONGER_TOLD, still_told=True)],
            findings=[{"kind": "addition", "note": f"A nova contagem inclui {BROUGHT_BACK}."}],
            brought_back=[BROUGHT_BACK],
        ),
        saying="Noemi e Orfa voltaram de Moabe para Belém, onde havia pão.",
    )

    assert body["findings_remaining"] == 0, (
        "um achado de addition que bate com o que foi trazido de volta tem de ser suprimido"
    )
    assert body["finding_kind"] is None


@pytest.mark.parametrize(
    ("carried", "shape"),
    [
        pytest.param("as duas coisas continuam ditas", "não é uma lista", id="not-a-list"),
        pytest.param(
            [{"element": NO_LONGER_TOLD}], "um item sem o campo de ainda dito", id="no-verdict"
        ),
    ],
)
@pytest.mark.asyncio
async def test_a_count_that_cannot_be_read_leaves_the_reported_findings_standing(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: ReaderOfTellings,
    caplog: pytest.LogCaptureFixture,
    carried: Any,
    shape: str,
) -> None:
    """An unreadable count is not a clean correction, and it is not an outage either.

    The reader still judged; only the counting came back in a shape the room cannot read. What
    it reported stands — dropping it would take a real loss off the list for good — and the
    room leaves a trace naming the condition, because a count silently ignored is a check the
    room believes it is running and is not.
    """
    with caplog.at_level(logging.WARNING, logger=ROOM_LOG):
        body, corrected = await _a_correction_verified_as(
            client,
            db_session,
            analyst,
            _a_reply_enumerating(
                carried,
                findings=[{"kind": "missing", "note": f"Não se diz mais que {NO_LONGER_TOLD}."}],
            ),
        )

    assert body["findings_remaining"] == 1, f"o que o leitor relatou vale, com {shape}"
    assert body["finding_kind"] == "missing"
    assert body["finding_segment_id"] == corrected.id

    traces = [
        record
        for record in caplog.records
        if record.name == ROOM_LOG and "enumera" in record.getMessage().lower()
    ]
    assert traces, (
        f"uma contagem ilegível ({shape}) tem de deixar rastro nomeando a condição; "
        f"o que foi registado: {[r.getMessage() for r in caplog.records if r.name == ROOM_LOG]}"
    )
