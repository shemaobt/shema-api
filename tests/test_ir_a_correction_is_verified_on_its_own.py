"""A correction is verified against the finding it answers, not by rereading the passage.

The first reading stays whole: the analyst's own prompt calls an element missing when it
appears in *no* stretch, which is a definition over the set, so a stretch on its own would be
reported as missing everything the others carry. What changes is the round after — when the
team has told one stretch back again to answer a finding the room already raised. That is a
question about one stretch, and it is asked about one stretch.

The rule these cases exist to hold: **wording varies, content does not.** The team retells by
speaking, in a language nobody here reads, transcribed by an imperfect ear. No honest retelling
repeats the earlier one word for word. A verifier strict with literal difference would refuse
almost every legitimate correction and trap the team re-recording without being told why —
which is the worst outcome available in a room where nobody reads.

These cases describe what the room does, never how it is stored: none of them names a table or
a column.
"""

from __future__ import annotations

import base64
import importlib
import json
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
#: Named rather than defaulted: the room's floor is English, and every telling in these
#: cases is Portuguese — a session left on the floor would meet the bridge-language gate.
LANGUAGE = "pt"

#: The heading that only the correction prompt carries. The double tells the two readings
#: apart by it, the way a reader would — not by counting calls.
CORRECTION_MARK = "## What the team told back now"
EARLIER_MARK = "## What the team told back before"
FINDING_MARK = "## The finding to verify"

#: What this passage carries, in the words the team uses for it. The double measures content
#: by these: a name outside the list, in the new telling, is something the map does not tell.
#: A test fixture, not a rule of the room — the room measures against the Meaning Map.
PASSAGE_ELEMENTS = frozenset({"Noemi", "Rute", "Orfa", "Belém", "Moabe", "Judá"})

#: Names from outside this passage. The map does not tell them, so a new telling that brings
#: one in has added something the map does not carry.
#:
#: A closed list rather than "any capitalised word the passage does not use": in speech
#: transcribed into sentences, the word that opens a sentence is capitalised too, and the
#: heuristic read "Foi" and "A" as people. A double that invents findings out of punctuation
#: would refuse exactly the honest, many-sentenced retellings this file exists to protect.
FOREIGN_NAMES = frozenset({"Jerusalém", "Egito", "Davi", "Jericó", "Salomão"})

_NAME = re.compile(r"\b[A-ZÁÉÍÓÚÂÊÔÃÕ][\wáéíóúâêôãõç]+")

FIRST_TELLING = "Noemi ouviu que havia pão em Belém e resolveu voltar de Moabe."
SECOND_TELLING = "Ela disse às duas noras que voltassem para a casa de suas mães."
THIRD_TELLING = "Rute disse que ia junto e não a deixaria."


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
    """The analyst, in both of its modes, and what each one was handed.

    The full reading answers with whatever the case set. The verification is **judged**, not
    dictated: it reads the finding, the earlier telling and the new one out of its own prompt
    and decides by content — which elements of the passage each telling carries — and never by
    how either one is worded. That is the calibration the room depends on, so a double that
    simply echoed a verdict back would leave every case here proving nothing about it.
    """

    def __init__(self) -> None:
        self.full_readings: list[str] = []
        self.verifications: list[str] = []
        self.answer = '{"evidence_sufficient": true, "findings": []}'

    async def __call__(self, *, system_prompt: str, user_content: str, **_: Any) -> str:
        if CORRECTION_MARK in system_prompt:
            self.verifications.append(system_prompt)
            return json.dumps(self._verify(system_prompt))
        self.full_readings.append(system_prompt)
        return self.answer

    def _verify(self, prompt: str) -> dict[str, Any]:
        finding = _section(prompt, FINDING_MARK, EARLIER_MARK)
        earlier = _section(prompt, EARLIER_MARK, CORRECTION_MARK)
        now = _section(prompt, CORRECTION_MARK, None)

        asked_about = _elements(finding)
        resolved = bool(asked_about) and asked_about <= _elements(now)

        findings: list[dict[str, str]] = []
        for lost in sorted(_elements(earlier) - _elements(now) - asked_about):
            findings.append({"kind": "missing", "note": f"{lost} não aparece mais neste trecho."})
        for added in sorted(_names(now) & FOREIGN_NAMES):
            findings.append({"kind": "addition", "note": f"{added} não é contado pelo mapa."})
        return {"resolved": resolved, "findings": findings}


def _section(prompt: str, start: str, end: str | None) -> str:
    """One block of the correction prompt, read off its heading."""
    if start not in prompt:
        return ""
    body = prompt.split(start, 1)[1]
    return body.split(end, 1)[0] if end and end in body else body


def _names(text: str) -> set[str]:
    return set(_NAME.findall(text))


def _elements(text: str) -> set[str]:
    return _names(text) & PASSAGE_ELEMENTS


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
    """The verdict speaker and the voice: a case here never depends on a missing model."""
    said: list[str] = []

    from app.api.internalization_room import back_translation as bt_api

    turn_module = importlib.import_module("app.services.internalization_room.run_turn")

    async def speaker(*, system_prompt: str, user_content: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return "No que você me contou, vamos olhar uma parte de novo."

    monkeypatch.setattr(turn_module, "call_agent", speaker)

    async def _voice(text: str, *_: Any, **__: Any):
        said.append(text)
        return (type("Voiced", (), {"key": f"clipe-{len(said)}"})(), 0)

    monkeypatch.setattr(bt_api.room, "synthesize_facilitator_speech", _voice)
    return said


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
    client: httpx.AsyncClient,
    session_id: str,
    segment: IRSegment,
    *,
    saying: str,
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


async def _three_stretches_told(client: httpx.AsyncClient) -> str:
    session_id = await _open_session(client)
    take_id = await _record(client, session_id)
    client.said.extend([FIRST_TELLING, SECOND_TELLING, THIRD_TELLING])  # type: ignore[attr-defined]
    for index in range(3):
        await _tell_back(
            client,
            session_id,
            take_id=take_id,
            starts_ms=index * 9000,
            ends_ms=(index + 1) * 9000,
        )
    return session_id


def _finding_on_the_first(note: str = "Orfa não apareceu neste trecho.") -> str:
    return json.dumps(
        {"evidence_sufficient": True, "findings": [{"kind": "missing", "chunk": 1, "note": note}]}
    )


async def _a_finding_raised_on_the_first_stretch(
    client: httpx.AsyncClient, db: AsyncSession, analyst: ReaderOfTellings
) -> tuple[str, IRSegment]:
    """The room reads the whole telling-back once and raises one finding on stretch one."""
    session_id = await _three_stretches_told(client)
    analyst.answer = _finding_on_the_first()
    first = await _finish(client, session_id)
    assert first.status_code == 200, first.text
    assert analyst.full_readings, "a primeira leitura tem de ter acontecido"
    standing = await service.final_segments(db, session_id)
    return session_id, standing[0]


@pytest.mark.asyncio
async def test_a_correction_is_verified_without_the_other_stretches(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: ReaderOfTellings
) -> None:
    """Acceptance 2. The question is about one stretch, so it is asked about one stretch."""
    session_id, first = await _a_finding_raised_on_the_first_stretch(client, db_session, analyst)

    await _tell_that_stretch_again(
        client, session_id, first, saying="Noemi e Orfa voltaram de Moabe para Belém."
    )
    answered = await _finish(client, session_id)

    assert answered.status_code == 200, answered.text
    assert analyst.verifications, "a correção tinha de ser verificada, não relida"
    asked = analyst.verifications[0]
    assert SECOND_TELLING not in asked
    assert THIRD_TELLING not in asked


@pytest.mark.asyncio
async def test_the_verification_is_given_the_earlier_telling(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: ReaderOfTellings
) -> None:
    """Acceptance 7. Without the earlier telling there is no way to ask "did something go?"."""
    session_id, first = await _a_finding_raised_on_the_first_stretch(client, db_session, analyst)
    corrected = "Noemi e Orfa voltaram de Moabe para Belém."

    await _tell_that_stretch_again(client, session_id, first, saying=corrected)
    await _finish(client, session_id)

    asked = analyst.verifications[0]
    assert FIRST_TELLING in asked
    assert corrected in asked


@pytest.mark.asyncio
async def test_an_accepted_correction_moves_the_team_past_that_finding(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: ReaderOfTellings
) -> None:
    """Acceptance 3. The finding is answered, so it stops being what the team hears."""
    session_id = await _three_stretches_told(client)
    analyst.answer = json.dumps(
        {
            "evidence_sufficient": True,
            "findings": [
                {"kind": "missing", "chunk": 1, "note": "Orfa não apareceu neste trecho."},
                {"kind": "missing", "chunk": 3, "note": "Judá não apareceu neste trecho."},
            ],
        }
    )
    first_answer = await _finish(client, session_id)
    assert first_answer.json()["findings_remaining"] == 2
    standing = await service.final_segments(db_session, session_id)

    await _tell_that_stretch_again(
        client, session_id, standing[0], saying="Noemi e Orfa voltaram de Moabe para Belém."
    )
    answered = await _finish(client, session_id)

    assert answered.status_code == 200, answered.text
    assert answered.json()["findings_remaining"] == 1
    assert answered.json()["finding_segment_id"] != standing[0].id


@pytest.mark.asyncio
async def test_a_refused_correction_gives_the_team_the_same_finding_back(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: ReaderOfTellings
) -> None:
    """Acceptance 4. Nothing was answered, so nothing moves on."""
    session_id, first = await _a_finding_raised_on_the_first_stretch(client, db_session, analyst)

    await _tell_that_stretch_again(
        client, session_id, first, saying="Noemi voltou de Moabe para Belém, e havia pão lá."
    )
    answered = await _finish(client, session_id)
    body = answered.json()
    standing = await service.final_segments(db_session, session_id)

    assert analyst.verifications, (
        "a correção tem de ter sido verificada: sem isto o caso fica verde sobre a releitura "
        "completa, que devolve o mesmo achado por outro caminho"
    )
    assert body["findings_remaining"] == 1
    assert body["finding_kind"] == "missing"
    assert body["finding_segment_id"] == standing[0].id
    assert body["checked"] is False


@pytest.mark.asyncio
async def test_retelling_a_stretch_in_other_words_is_not_a_refusal(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: ReaderOfTellings
) -> None:
    """Acceptance 3, and the control the whole slice turns on.

    The team retells by speaking, transcribed by an imperfect ear. This correction answers the
    finding while sharing almost no wording with the telling it replaces — other words, another
    order, one extra detail of form. A verifier comparing literally would refuse it and trap the
    team re-recording without being told why. The calibration has to be in the prompt itself,
    so this case reads the production prompt for it as well as watching the outcome.
    """
    session_id, first = await _a_finding_raised_on_the_first_stretch(client, db_session, analyst)
    in_other_words = (
        "Foi assim: as duas moças, Orfa e a outra, estavam com a sogra delas. "
        "A mulher tinha sabido que lá na terra dela, em Belém, já tinha o que comer, "
        "e por isso saiu de Moabe. Noemi, esse é o nome dela."
    )

    await _tell_that_stretch_again(client, session_id, first, saying=in_other_words)
    # The closing reading is not what this case is about, so it is told to find nothing: what
    # is under test is whether the verification accepted the retelling, not what a whole
    # reading makes of the passage afterwards.
    analyst.answer = '{"evidence_sufficient": true, "findings": []}'
    answered = await _finish(client, session_id)
    body = answered.json()

    assert len(analyst.full_readings) == 2, (
        "só uma lista esvaziada pela verificação chega à leitura final, então chegar lá é a "
        "prova de que a correção foi aceita — recusá-la prende a equipe num laço de regravar "
        "sem entender o motivo"
    )
    assert body["findings_remaining"] == 0
    asked = analyst.verifications[0]
    assert "wording" in asked.lower()


@pytest.mark.asyncio
async def test_losing_an_element_is_refused_even_when_the_finding_was_answered(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: ReaderOfTellings
) -> None:
    """Acceptance 5. The regression the earlier telling is carried along to catch.

    Retelling one stretch can quietly drop something only that stretch carried, turning an
    answered finding into a new hole. Comparing against the version it replaced catches it
    without rereading anything else.
    """
    session_id, first = await _a_finding_raised_on_the_first_stretch(client, db_session, analyst)

    await _tell_that_stretch_again(
        client, session_id, first, saying="Orfa estava lá com a sogra dela."
    )
    answered = await _finish(client, session_id)
    body = answered.json()

    assert analyst.verifications, (
        "a perda tem de ter sido vista pela verificação, e não pela releitura completa"
    )
    assert body["findings_remaining"] >= 1
    assert body["checked"] is False
    assert (
        body["finding_segment_id"] == (await service.final_segments(db_session, session_id))[0].id
    )
    assert "Orfa" not in (spoken_note := body["finding_kind"] or "") + spoken_note, (
        "o achado original foi respondido; o que sobra é o que a recontagem deixou cair"
    )


@pytest.mark.asyncio
async def test_the_first_reading_still_gets_every_stretch(
    client: httpx.AsyncClient, analyst: ReaderOfTellings
) -> None:
    """Acceptance 1. The control against this slice leaking into discovery.

    "Missing" is defined over the whole set, so a first reading given one stretch would report
    as missing everything the others carry.
    """
    session_id = await _three_stretches_told(client)

    answered = await _finish(client, session_id)

    assert answered.status_code == 200, answered.text
    assert analyst.verifications == [], "a primeira leitura não é uma verificação"
    read = analyst.full_readings[0]
    assert FIRST_TELLING in read
    assert SECOND_TELLING in read
    assert THIRD_TELLING in read


@pytest.mark.asyncio
async def test_bringing_in_what_the_map_does_not_tell_is_refused(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: ReaderOfTellings
) -> None:
    """Acceptance 6 of the issue, which the Testing Plan did not carry a case for.

    The mirror of losing an element: a retelling can answer the finding and bring in something
    the map never tells, and outside detail entering a translation is the failure the whole
    back-translation exists to catch. It is also the positive control for the double's own
    `addition` rule — without a case that reaches it, nothing would say whether that rule can
    fire at all.
    """
    session_id, first = await _a_finding_raised_on_the_first_stretch(client, db_session, analyst)

    await _tell_that_stretch_again(
        client,
        session_id,
        first,
        saying="Noemi e Orfa voltaram de Moabe para Belém, que fica perto de Jerusalém.",
    )
    answered = await _finish(client, session_id)
    body = answered.json()

    assert analyst.verifications, "a correção tem de ter sido verificada"
    assert body["findings_remaining"] >= 1
    assert body["checked"] is False
    assert body["finding_kind"] == "addition"


# ---------------------------------------------------------------------------
# The passage is only checked after a clean whole reading — ENG-680
# ---------------------------------------------------------------------------
#
# Verifying corrections one stretch at a time is cheap and right for "did this finding go?",
# but it sees a piece of the set. Two things escape it: a correction can answer, by accident,
# a finding raised on another stretch; and whether the telling-back as a whole is too thin to
# judge only exists looking at all of it. So the last word is always a whole reading — the
# fast test while you work, the whole suite before you close.


async def _the_last_finding_answered(
    client: httpx.AsyncClient, db: AsyncSession, analyst: ReaderOfTellings
) -> str:
    """One finding, raised whole and answered by a correction the verification accepts.

    Leaves the room at exactly the moment this slice is about: nothing is outstanding, and
    nothing but stretch-by-stretch verification has looked at the work since the first reading.
    """
    session_id, first = await _a_finding_raised_on_the_first_stretch(client, db, analyst)
    await _tell_that_stretch_again(
        client, session_id, first, saying="Noemi e Orfa voltaram de Moabe para Belém."
    )
    return session_id


@pytest.mark.asyncio
async def test_clean_verifications_do_not_check_the_passage_on_their_own(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: ReaderOfTellings
) -> None:
    """Acceptance 1, and the case the whole slice rests on.

    A verification answers the finding it was shown and nothing else. Letting it close the
    passage would strike it off the wheel for good — there is no undo — on the word of a
    reading that never saw the other stretches.
    """
    session_id = await _the_last_finding_answered(client, db_session, analyst)
    analyst.answer = '{"evidence_sufficient": true, "findings": []}'

    answered = await _finish(client, session_id)

    assert answered.status_code == 200, answered.text
    assert len(analyst.full_readings) == 2, (
        "sem uma leitura completa depois da última correção, a passagem estaria sendo "
        "conferida pela palavra de quem só viu um trecho"
    )
    closing_reading = analyst.full_readings[-1]
    assert SECOND_TELLING in closing_reading
    assert THIRD_TELLING in closing_reading


@pytest.mark.asyncio
async def test_a_closing_reading_that_finds_something_sends_the_team_back(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: ReaderOfTellings
) -> None:
    """Acceptance 2. What only the whole reading can see reaches the team like anything else."""
    session_id = await _the_last_finding_answered(client, db_session, analyst)
    analyst.answer = json.dumps(
        {
            "evidence_sufficient": True,
            "findings": [{"kind": "missing", "chunk": 3, "note": "Judá não apareceu."}],
        }
    )

    answered = await _finish(client, session_id)
    body = answered.json()

    assert body["checked"] is False
    assert body["findings_remaining"] == 1
    assert body["finding_kind"] == "missing"


@pytest.mark.asyncio
async def test_a_clean_closing_reading_checks_the_passage(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: ReaderOfTellings
) -> None:
    """Acceptance 3. The gate is a gate, not a wall: a clean whole reading does close it."""
    session_id = await _the_last_finding_answered(client, db_session, analyst)
    analyst.answer = '{"evidence_sufficient": true, "findings": []}'

    answered = await _finish(client, session_id)
    body = answered.json()

    assert body["checked"] is True
    assert body["findings_remaining"] == 0
    assert len(analyst.full_readings) == 2, (
        "e é a leitura completa que a conferiu, não a verificação"
    )


@pytest.mark.asyncio
async def test_the_closing_reading_is_not_paid_for_twice(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: ReaderOfTellings
) -> None:
    """Acceptance 4, and a control on cost.

    Without it the gate becomes a whole reading on every press, and the expense the
    stretch-by-stretch verification just removed walks back in through the side door.
    """
    session_id = await _the_last_finding_answered(client, db_session, analyst)
    analyst.answer = '{"evidence_sufficient": true, "findings": []}'
    await _finish(client, session_id)
    readings_when_it_closed = len(analyst.full_readings)
    verifications_when_it_closed = len(analyst.verifications)

    again = await _finish(client, session_id)

    assert again.json()["checked"] is True
    assert len(analyst.full_readings) == readings_when_it_closed, (
        "nada mudou desde a leitura que conferiu, então não há nada novo para ler"
    )
    assert len(analyst.verifications) == verifications_when_it_closed, (
        "e nada novo para verificar tampouco"
    )


@pytest.mark.asyncio
async def test_a_team_that_got_it_right_first_time_pays_for_one_reading(
    client: httpx.AsyncClient, analyst: ReaderOfTellings
) -> None:
    """Acceptance 3 read from the other side, and a control on fairness.

    The gate exists because verifications see a piece of the set. A first reading is not a
    piece of anything — it already saw all of it. Charging that team a second whole reading
    would punish exactly the path the room wants.
    """
    session_id = await _three_stretches_told(client)
    analyst.answer = '{"evidence_sufficient": true, "findings": []}'

    answered = await _finish(client, session_id)
    body = answered.json()

    assert body["checked"] is True
    assert body["findings_remaining"] == 0
    assert len(analyst.full_readings) == 1
    assert analyst.verifications == []
