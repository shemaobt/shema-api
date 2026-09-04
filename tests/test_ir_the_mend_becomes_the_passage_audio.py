"""A stretch re-recorded in the mother tongue becomes a new recording of the whole passage.

The room could already correct one stretch: the team records that stretch again, it is kept as
a rehearsal recording of its own, and the stretch comes to point at it. What nobody could do
afterwards was *hear the passage* — the corrected minute lived in one file and everything
around it in another, so playing the passage meant resolving stretch by stretch and stitching
by hand. The product asked for the other thing three times: one recording, updated.

So the room rebuilds it. The recording the stretch lived in, with the corrected stretch's audio
put where the old one was, is kept as a rehearsal recording like any other, and every stretch
that still counts comes to be a slice of *that* file — the ones before it where they were, the
ones after it moved by however much the passage grew or shrank. The invariant the segment was
introduced for survives untouched: a stretch is a slice of one file, never a position over a
concatenated passage.

Rebuilding needs an encoder and a bucket, and neither of those is allowed to cost the team
their correction. When it cannot be done the correction stands exactly as it did before, on its
own recording, and the answer says so.

These cases describe what the room does, and read it where a tablet reads it. The one exception
is the stretches that stopped counting: they are the history the room keeps and no route serves
them, so the case about not throwing the team's work away asks the room's own reading of them
directly. The two stand-ins are the bucket, which the room's own tests already hold still, and
the rebuilding itself, which is an encoder in a subprocess — case 9 is the one that runs it for
real.
"""

from __future__ import annotations

import base64
import importlib
import json
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import httpx
import pytest
from google_crc32c import Checksum
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRTakeKind
from app.services.internalization_room import segments as service
from app.services.platform.storage import StoredObject

PREFIX = "/api/internalization-room"
KEY = "sala-de-teste"
DEVICE = "tablet-da-equipe-1"
PASSAGE = "P01"
#: Named rather than left on the floor, which is English: every telling in these cases is
#: Portuguese, and the room's bridge-language gate reads what it is given.
LANGUAGE = "pt"
HEADERS = {"X-Room-Key": KEY, "X-Room-Device": DEVICE}

#: The three stretches the team tells back, over one recording of the passage.
FIRST = (0, 5000)
SECOND = (5000, 12000)
THIRD = (12000, 20000)

#: Distinct bytes, so a case can say *which* recording reached the rebuilding and which one
#: reached the bucket, rather than only that something did.
PASSAGE_AUDIO = b"o ensaio inteiro da passagem, gravado pela equipe"
CORRECTED_AUDIO = b"so o segundo trecho, gravado de novo, mais longo"
CORRECTED_AGAIN = b"e agora o terceiro trecho, gravado de novo"

#: How long the re-recorded stretches are. The app sends the new stretch as the whole of its
#: own recording, so the room learns the duration from the slice it is asked for.
CORRECTED_MS = 9000
CORRECTED_AGAIN_MS = 5000


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


class Rebuilder:
    """A stand-in for the encoder, which records what it was handed and marks what it returns.

    Marked, so a case can point at the recording that came out of it wherever that recording
    ends up — in the bucket, in the packet, or under the next correction — without knowing how
    the room names or stores it. Numbered, so two rebuildings are told apart.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[bytes, bytes, int, int]] = []
        self.took: list[tuple[int, int | None]] = []
        self.refuses = False

    async def __call__(
        self,
        original: bytes,
        corrected: bytes,
        *,
        starts_ms: int,
        ends_ms: int,
        corrected_starts_ms: int = 0,
        corrected_ends_ms: int | None = None,
    ) -> bytes:
        self.calls.append((original, corrected, starts_ms, ends_ms))
        self.took.append((corrected_starts_ms, corrected_ends_ms))
        if self.refuses:
            raise RuntimeError("o encoder nao respondeu")
        return b"<passagem-refeita-%d>" % len(self.calls) + original + b"|" + corrected


@pytest.fixture()
async def bucket(monkeypatch: pytest.MonkeyPatch) -> MemoryStore:
    from app.services.internalization_room import takes as takes_service

    store = MemoryStore()
    monkeypatch.setattr(takes_service, "_store", lambda *_, **__: store)
    return store


@pytest.fixture()
def rebuilder(monkeypatch: pytest.MonkeyPatch) -> Rebuilder:
    """The rebuilding of the passage, held still. Case 9 is the one that runs the real thing."""
    compose_module = importlib.import_module("app.services.internalization_room.compose")

    stand_in = Rebuilder()
    monkeypatch.setattr(compose_module, "compose_passage", stand_in)
    return stand_in


@pytest.fixture()
def voice(monkeypatch: pytest.MonkeyPatch) -> None:
    """The analyst, the speaker and the synthesizer, so `terminei` answers with no model.

    Asked for by the one case that presses it, rather than standing over all of them: a double
    installed for eight cases that never reach it says those cases depend on a model, and they
    do not.
    """
    from app.api.internalization_room import back_translation as bt_api
    from app.services.internalization_room import back_translation as bt_service

    turn_module = importlib.import_module("app.services.internalization_room.run_turn")

    async def _reads(**_: Any) -> str:
        return '{"evidence_sufficient": true, "findings": []}'

    async def _speaks(*, system_prompt: str, user_content: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return "Vocês contaram bem."

    async def _synthesizes(text: str, *_: Any, **__: Any):
        return (type("Voiced", (), {"key": "clipe-do-veredito"})(), 0)

    monkeypatch.setattr(bt_service, "call_agent", _reads)
    monkeypatch.setattr(turn_module, "call_agent", _speaks)
    monkeypatch.setattr(bt_api.room, "synthesize_facilitator_speech", _synthesizes)


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


# ---------------------------------------------------------------------------
# What a tablet does, in the room's own words
# ---------------------------------------------------------------------------


async def _open(client: httpx.AsyncClient) -> str:
    made = await client.post(
        f"{PREFIX}/sessions",
        headers={"X-Room-Key": KEY},
        json={"pericope": PASSAGE, "language": LANGUAGE},
    )
    assert made.status_code == 200, made.text
    return str(made.json()["session_id"])


async def _rehearse(client: httpx.AsyncClient, session_id: str, audio: bytes, scope: str) -> str:
    """Keep one mother-tongue recording: the whole passage, or one stretch of it re-recorded."""
    kept = await client.post(
        f"{PREFIX}/sessions/{session_id}/takes",
        headers=HEADERS,
        data={"kind": IRTakeKind.ENSAIO.value, "scope": scope},
        files={"file": ("tomada.m4a", audio, "audio/mp4")},
    )
    assert kept.status_code == 200, kept.text
    return str(kept.json()["take_id"])


async def _tell(
    client: httpx.AsyncClient, session_id: str, take_id: str, span: tuple[int, int], saying: str
) -> None:
    client.said.append(saying)  # type: ignore[attr-defined]
    told = await client.post(
        f"{PREFIX}/sessions/{session_id}/back-translation/chunks",
        headers=HEADERS,
        data={"take_id": take_id, "starts_ms": str(span[0]), "ends_ms": str(span[1])},
        files={"file": (f"trecho-{span[0]}.m4a", b"contado: %d" % span[0], "audio/mp4")},
    )
    assert told.status_code == 200, told.text


async def _replace(
    client: httpx.AsyncClient,
    session_id: str,
    segment_id: str,
    *,
    take_id: str,
    starts_ms: int,
    ends_ms: int,
    audio: bytes | None = None,
) -> httpx.Response:
    files = {"file": ("de-novo.m4a", audio, "audio/mp4")} if audio is not None else None
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/segments/{segment_id}/replace",
        headers=HEADERS,
        data={"take_id": take_id, "starts_ms": str(starts_ms), "ends_ms": str(ends_ms)},
        files=files,
    )


async def _units(client: httpx.AsyncClient, session_id: str) -> list[dict[str, Any]]:
    """The stretches that count, read the way a tablet picking the session back up reads them."""
    state = await client.get(f"{PREFIX}/sessions/{session_id}", headers={"X-Room-Key": KEY})
    assert state.status_code == 200, state.text
    return list(state.json()["back_translation"]["segments"])


async def _takes(client: httpx.AsyncClient, session_id: str) -> list[dict[str, Any]]:
    listed = await client.get(f"{PREFIX}/sessions/{session_id}/takes", headers={"X-Room-Key": KEY})
    assert listed.status_code == 200, listed.text
    return list(listed.json()["takes"])


def _spans(units: list[dict[str, Any]]) -> list[tuple[str, int, int]]:
    return [(one["take_id"], one["starts_ms"], one["ends_ms"]) for one in units]


async def _three_stretches_over_one_recording(client: httpx.AsyncClient) -> tuple[str, str]:
    """A session with the passage rehearsed once and told back in three stretches."""
    session_id = await _open(client)
    take_id = await _rehearse(client, session_id, PASSAGE_AUDIO, PASSAGE)
    await _tell(client, session_id, take_id, FIRST, "Noemi resolveu voltar para Belém.")
    await _tell(client, session_id, take_id, SECOND, "Orfa voltou para o povo dela.")
    await _tell(client, session_id, take_id, THIRD, "Rute disse que ia junto com Noemi.")
    return session_id, take_id


async def _correct_the_second_stretch(
    client: httpx.AsyncClient, session_id: str
) -> tuple[httpx.Response, str]:
    """The team records the middle stretch again in the mother tongue, and sends it.

    That is the long road the room already had: the new mother tongue is kept as a recording
    of its own, and the stretch is asked to point at the whole of it.
    """
    corrected = await _rehearse(client, session_id, CORRECTED_AUDIO, "trecho-2")
    middle = (await _units(client, session_id))[1]
    answered = await _replace(
        client,
        session_id,
        middle["segment_id"],
        take_id=corrected,
        starts_ms=0,
        ends_ms=CORRECTED_MS,
    )
    assert answered.status_code == 200, answered.text
    return answered, corrected


# ---------------------------------------------------------------------------
# Everything a session needs before its packet is allowed to travel
# ---------------------------------------------------------------------------


async def _releasable_session(client: httpx.AsyncClient, db: AsyncSession) -> str:
    """The three stretches, over a session that has done everything else a release asks for.

    Comprehension supported, consent given, coverage satisfied. Written straight onto the
    session rather than played out through the room: none of it is what these cases are about,
    and the release's own suite is where those gates are held.
    """
    from app.services.internalization_room.canon.elements import element_keys
    from app.services.internalization_room.comprehension.checkpoints import (
        checkpoints_for,
        scene_ids_for,
    )
    from app.services.internalization_room.comprehension.evidence import (
        EvidenceMethod,
        EvidenceObservation,
        EvidenceResult,
    )
    from app.services.internalization_room.comprehension.state import ComprehensionState
    from app.services.internalization_room.coverage import initial_state, merge
    from app.services.internalization_room.sessions import get_session, save_comprehension

    session_id, _ = await _three_stretches_over_one_recording(client)
    session = await get_session(db, session_id)
    session.coverage_state = merge(
        initial_state(PASSAGE), pericope_num=PASSAGE, engaged=element_keys(PASSAGE)
    )
    await save_comprehension(
        db,
        session,
        ComprehensionState(
            ledger=[
                EvidenceObservation(
                    id=f"ev-{index}",
                    unit_id=checkpoint.id,
                    probe_id=f"probe-{index}",
                    method=EvidenceMethod.MICRO_TELLBACK,
                    result=EvidenceResult.DEMONSTRATED,
                )
                for index, checkpoint in enumerate(checkpoints_for(PASSAGE))
            ],
            practiced_scene_ids=scene_ids_for(PASSAGE),
            recording_consent_given=True,
        ),
    )
    return session_id


async def _tell_that_stretch_again(
    client: httpx.AsyncClient, session_id: str, *, index: int
) -> None:
    """Explain a stretch whose mother tongue was just re-recorded, over the audio it now has.

    The second half of the room's own correction: a re-recorded stretch is born carrying
    nothing the team said, and a packet does not travel with a wordless stretch in it.
    """
    unit = (await _units(client, session_id))[index]
    client.said.append("Orfa voltou para Moabe, para o povo dela.")  # type: ignore[attr-defined]
    answered = await _replace(
        client,
        session_id,
        unit["segment_id"],
        take_id=unit["take_id"],
        starts_ms=unit["starts_ms"],
        ends_ms=unit["ends_ms"],
        audio=b"a ponte da correcao",
    )
    assert answered.status_code == 200, answered.text


async def _finish(
    client: httpx.AsyncClient, session_id: str, *, units: list[dict[str, Any]]
) -> None:
    """`terminei`, with a report of having played the passage the session now stands on."""
    whole = max(one["ends_ms"] for one in units)
    answered = await client.post(
        f"{PREFIX}/sessions/{session_id}/back-translation/finish",
        headers={"X-Room-Key": KEY},
        json={"played_ranges": [[0, whole]], "clip_duration_ms": whole},
    )
    assert answered.status_code == 200, answered.text


async def _release(db: AsyncSession, session_id: str) -> dict[str, Any]:
    from app.services.internalization_room.release import build_internalization_release
    from app.services.internalization_room.sessions import get_session

    return await build_internalization_release(db, await get_session(db, session_id))


# ---------------------------------------------------------------------------
# 1. Correcting a stretch in the mother tongue rebuilds the passage
# ---------------------------------------------------------------------------


async def test_a_stretch_re_recorded_in_the_mother_tongue_rebuilds_the_passage(
    client: httpx.AsyncClient, bucket: MemoryStore, rebuilder: Rebuilder
) -> None:
    """The recording the stretch lived in, with the corrected audio put where the old was.

    The team hears the passage by playing one file, which is what was asked for. What proves
    it is not "a file exists" but *which* audio went into it and where every stretch landed:
    the rebuilding is handed the passage and the correction with the slice being cut out, and
    the three stretches come back as slices of the one recording that came out — the first
    where it was, the corrected one as long as its new audio, the last moved by the difference.
    """
    session_id, take_id = await _three_stretches_over_one_recording(client)

    _, corrected = await _correct_the_second_stretch(client, session_id)

    assert rebuilder.calls == [(PASSAGE_AUDIO, CORRECTED_AUDIO, 5000, 12000)], (
        "a passagem e a correção, e o trecho a ser tirado do lugar"
    )
    rebuilt = rebuilder.calls[0]
    made = b"<passagem-refeita-1>" + rebuilt[0] + b"|" + rebuilt[1]
    assert made in bucket.objects.values(), "o que saiu da remontagem foi guardado"

    units = await _units(client, session_id)
    passage = {one["take_id"] for one in units}
    assert len(passage) == 1, "os três trechos são fatias de um arquivo só"
    whole = passage.pop()
    assert whole not in {take_id, corrected}, "e esse arquivo é novo: nem o ensaio, nem a correção"
    assert _spans(units) == [
        (whole, 0, 5000),
        (whole, 5000, 14000),
        (whole, 14000, 22000),
    ]


# ---------------------------------------------------------------------------
# 2. The answer says what was rebuilt, so the tablet can swap the part
# ---------------------------------------------------------------------------


async def test_the_answer_to_a_correction_names_the_rebuilt_passage(
    client: httpx.AsyncClient, rebuilder: Rebuilder
) -> None:
    """The app sent the correction and has to know what to play now.

    Told only that the stretch was taken, it would go on playing the recording it had, which is
    the passage without the correction in it. So the answer names the recording that replaced
    it and hands back every stretch against it, in one reply.
    """
    session_id, take_id = await _three_stretches_over_one_recording(client)

    answered, corrected = await _correct_the_second_stretch(client, session_id)

    said = answered.json()
    rebuilt = said["composed_take_id"]
    assert rebuilt is not None, "a resposta diz qual gravação da passagem vale agora"
    assert rebuilt not in {take_id, corrected}
    assert _spans(said["segments"]) == [
        (rebuilt, 0, 5000),
        (rebuilt, 5000, 14000),
        (rebuilt, 14000, 22000),
    ]


# ---------------------------------------------------------------------------
# 3. Redoing only the explanation rebuilds nothing
# ---------------------------------------------------------------------------


async def test_telling_a_stretch_back_again_leaves_the_recording_alone(
    client: httpx.AsyncClient, rebuilder: Rebuilder
) -> None:
    """The other correction the product has: the same audio, explained again.

    Nothing about the mother tongue moved, so there is nothing to rebuild — and rebuilding
    anyway would spend an encoder and hand the team a new file identical to the one they have.
    """
    session_id, take_id = await _three_stretches_over_one_recording(client)
    before = await _units(client, session_id)

    client.said.append("Orfa voltou para Moabe, para o povo dela.")  # type: ignore[attr-defined]
    answered = await _replace(
        client,
        session_id,
        before[1]["segment_id"],
        take_id=take_id,
        starts_ms=SECOND[0],
        ends_ms=SECOND[1],
        audio=b"a ponte contada outra vez",
    )

    assert answered.status_code == 200, answered.text
    assert rebuilder.calls == [], "nada foi remontado"
    assert _spans(await _units(client, session_id)) == _spans(before), (
        "nenhum trecho mudou de arquivo nem de lugar dentro dele"
    )


# ---------------------------------------------------------------------------
# 4. A tablet picking the session back up gets the stretches over the rebuilt passage
# ---------------------------------------------------------------------------


async def test_a_session_resumed_after_a_correction_hands_back_the_rebuilt_passage(
    client: httpx.AsyncClient, rebuilder: Rebuilder
) -> None:
    """The app keeps none of this across a restart, so what the room says is all there is.

    A tablet that came back to a corrected session and was handed the old recording would show
    the team the passage with the mistake still in it, and would have no way to know.
    """
    session_id, _ = await _three_stretches_over_one_recording(client)
    answered, _ = await _correct_the_second_stretch(client, session_id)
    rebuilt = answered.json()["composed_take_id"]

    resumed = await _units(client, session_id)

    assert _spans(resumed) == [
        (rebuilt, 0, 5000),
        (rebuilt, 5000, 14000),
        (rebuilt, 14000, 22000),
    ]


# ---------------------------------------------------------------------------
# 5. The packet that travels to Refine carries the rebuilt passage
# ---------------------------------------------------------------------------


async def test_the_packet_for_refine_carries_the_rebuilt_passage(
    client: httpx.AsyncClient, db_session: AsyncSession, rebuilder: Rebuilder, voice: None
) -> None:
    """Whoever reviews the session downstream resolves stretches against the recording named.

    A packet that named the old one would send a reviewer to audio the team had already
    corrected, and nothing in it would say so. The recordings the session went through stay
    listed: they are the history of how the team got there, and the room deletes no take.
    """
    session_id = await _releasable_session(client, db_session)
    answered, _ = await _correct_the_second_stretch(client, session_id)
    rebuilt = answered.json()["composed_take_id"]
    await _tell_that_stretch_again(client, session_id, index=1)
    await _finish(client, session_id, units=await _units(client, session_id))

    packet = await _release(db_session, session_id)

    told = packet["back_translation"]["segments"]
    assert len(told) == 3
    assert {one["take_id"] for one in told} == {rebuilt}
    rehearsals = [one for one in packet["audio"]["rehearsal_takes"] if one["take_id"] == rebuilt]
    assert len(rehearsals) == 1, "a passagem refeita viaja como ensaio, e é uma só"


# ---------------------------------------------------------------------------
# 6. A second correction is built on the passage the first one made
# ---------------------------------------------------------------------------


async def test_a_second_correction_is_built_on_the_passage_the_first_one_made(
    client: httpx.AsyncClient, rebuilder: Rebuilder
) -> None:
    """Corrections do not accumulate as files to stitch: there is always one passage.

    The second rebuilding is handed the recording the first one made, and the slice it cuts is
    where the stretch sits *in that* recording — not where it sat before anybody corrected
    anything. Handed the original instead, the room would silently undo the first correction.
    """
    session_id, _ = await _three_stretches_over_one_recording(client)
    await _correct_the_second_stretch(client, session_id)
    once = b"<passagem-refeita-1>" + PASSAGE_AUDIO + b"|" + CORRECTED_AUDIO

    again = await _rehearse(client, session_id, CORRECTED_AGAIN, "trecho-3")
    last = (await _units(client, session_id))[2]
    answered = await _replace(
        client,
        session_id,
        last["segment_id"],
        take_id=again,
        starts_ms=0,
        ends_ms=CORRECTED_AGAIN_MS,
    )

    assert answered.status_code == 200, answered.text
    assert rebuilder.calls[1] == (once, CORRECTED_AGAIN, 14000, 22000)
    twice = answered.json()["composed_take_id"]
    assert _spans(await _units(client, session_id)) == [
        (twice, 0, 5000),
        (twice, 5000, 14000),
        (twice, 14000, 19000),
    ]


# ---------------------------------------------------------------------------
# 7. Nothing the team recorded is thrown away
# ---------------------------------------------------------------------------


async def test_a_correction_throws_none_of_the_team_s_own_recordings_away(
    client: httpx.AsyncClient, db_session: AsyncSession, rebuilder: Rebuilder
) -> None:
    """The room deletes no recording and erases no telling.

    A rebuilt passage is a recording made *from* what the team did, not a replacement for it:
    a reviewer who has to go back to what was actually said in the room needs both files, and
    the stretch as it stood before the correction is the history the packet carries.
    """
    session_id, take_id = await _three_stretches_over_one_recording(client)
    before = (await _units(client, session_id))[1]

    _, corrected = await _correct_the_second_stretch(client, session_id)

    kept = {one["take_id"] for one in await _takes(client, session_id)}
    assert {take_id, corrected} <= kept, "o ensaio e a regravação continuam lá"
    retired = await service.retired_segments(db_session, session_id)
    assert before["segment_id"] in {one.id for one in retired}
    assert [one.transcript for one in retired] == ["Orfa voltou para o povo dela."], (
        "o que a equipe tinha contado daquele trecho continua guardado"
    )


# ---------------------------------------------------------------------------
# 8. A rebuilding that fails costs the team nothing
# ---------------------------------------------------------------------------


async def test_a_correction_survives_a_rebuilding_that_could_not_be_done(
    client: httpx.AsyncClient, rebuilder: Rebuilder, caplog: pytest.LogCaptureFixture
) -> None:
    """An encoder or a bucket that went away must not take the team's correction with it.

    So the correction lands exactly as it did before any of this: the stretch on its own
    recording, the others where they were. The answer names no rebuilt passage, which is how
    the app knows to go on playing stretch by stretch, and the room leaves a warning naming
    the session and the stretch so somebody can come and look.
    """
    session_id, take_id = await _three_stretches_over_one_recording(client)
    rebuilder.refuses = True
    middle = (await _units(client, session_id))[1]

    with caplog.at_level(logging.WARNING):
        corrected = await _rehearse(client, session_id, CORRECTED_AUDIO, "trecho-2")
        answered = await _replace(
            client,
            session_id,
            middle["segment_id"],
            take_id=corrected,
            starts_ms=0,
            ends_ms=CORRECTED_MS,
        )

    assert answered.status_code == 200, answered.text
    assert answered.json()["composed_take_id"] is None, "a resposta diz que não refez a passagem"
    assert _spans(await _units(client, session_id)) == [
        (take_id, 0, 5000),
        (corrected, 0, CORRECTED_MS),
        (take_id, 12000, 20000),
    ], "a correção ficou de pé, do jeito que ficava antes"
    complained = [
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.WARNING
        and session_id in record.getMessage()
        and middle["segment_id"] in record.getMessage()
    ]
    assert complained, "o aviso nomeia a sessão e o trecho"


# ---------------------------------------------------------------------------
# 10. Only the slice the correction was addressed by goes into the passage
# ---------------------------------------------------------------------------


async def test_only_the_addressed_slice_of_the_correction_enters_the_passage(
    client: httpx.AsyncClient, rebuilder: Rebuilder
) -> None:
    """The team's new recording is addressed like any other: a slice of a file, not a file.

    An app that trims the silence off its own recording sends a stretch shorter than the file
    it lives in — and the passage has to grow by the stretch, not by the file. Splicing the
    whole recording in while moving everything after it by the stretch would misaddress the
    rest of the passage by the difference, silently, and compound it on the next correction.
    """
    session_id, _ = await _three_stretches_over_one_recording(client)
    corrected = await _rehearse(client, session_id, CORRECTED_AUDIO, "trecho-2")
    middle = (await _units(client, session_id))[1]

    answered = await _replace(
        client,
        session_id,
        middle["segment_id"],
        take_id=corrected,
        starts_ms=400,
        ends_ms=400 + CORRECTED_MS,
    )

    assert answered.status_code == 200, answered.text
    assert rebuilder.took == [(400, 400 + CORRECTED_MS)], (
        "a remontagem recebe a fatia que a equipe endereçou, não o arquivo inteiro"
    )
    rebuilt = answered.json()["composed_take_id"]
    assert _spans(await _units(client, session_id)) == [
        (rebuilt, 0, 5000),
        (rebuilt, 5000, 14000),
        (rebuilt, 14000, 22000),
    ], "a passagem cresceu pelo trecho, e não pelo arquivo em que ele estava"


# ---------------------------------------------------------------------------
# 11. A stretch the team divided moves with the stretches it was divided into
# ---------------------------------------------------------------------------


async def test_a_divided_stretch_moves_with_the_pieces_it_was_divided_into(
    client: httpx.AsyncClient, db_session: AsyncSession, rebuilder: Rebuilder
) -> None:
    """The correction sits *inside* the stretch the team divided, which is a third position.

    A stretch before the correction does not move and one after it moves whole; a divided one
    containing it keeps its start and gains the difference, because it still has to describe
    exactly the audio its own pieces cover. Left where it was, it would name a span of the
    rebuilt passage that runs short of its last piece — and it travels to Refine as what the
    team said before they heard two ideas in it.
    """
    session_id, _ = await _three_stretches_over_one_recording(client)
    middle = (await _units(client, session_id))[1]
    cut = await client.post(
        f"{PREFIX}/sessions/{session_id}/segments/{middle['segment_id']}/divide",
        headers=HEADERS,
        json={"at_ms": 8000},
    )
    assert cut.status_code == 200, cut.text

    corrected = await _rehearse(client, session_id, CORRECTED_AUDIO, "primeira-metade")
    first_half = (await _units(client, session_id))[1]
    answered = await _replace(
        client,
        session_id,
        first_half["segment_id"],
        take_id=corrected,
        starts_ms=0,
        ends_ms=CORRECTED_MS,
    )

    assert answered.status_code == 200, answered.text
    rebuilt = answered.json()["composed_take_id"]
    assert _spans(await _units(client, session_id)) == [
        (rebuilt, 0, 5000),
        (rebuilt, 5000, 14000),
        (rebuilt, 14000, 18000),
        (rebuilt, 18000, 26000),
    ]
    divided = await service.divided_segments(db_session, session_id)
    assert [(one.take_id, one.starts_ms, one.ends_ms) for one in divided] == [
        (rebuilt, 5000, 18000)
    ], "o trecho dividido cobre exatamente o que as suas partes cobrem"


# ---------------------------------------------------------------------------
# 12. A database that fails mid-rebuilding costs the team nothing either
# ---------------------------------------------------------------------------


async def test_a_correction_survives_a_database_that_failed_mid_rebuilding(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    rebuilder: Rebuilder,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The other way rebuilding can fail, and the one that leaves the room holding something.

    An encoder that went away leaves nothing behind; a database that failed part-way leaves the
    session unusable until somebody says so, and the very next thing the room does is read the
    stretches back to answer the team. Answered with a 500 they would retry, and the retry is
    refused — the stretch no longer counts, because their correction was written before any of
    this. So the team would be told, on a screen that cannot explain, that a correction the
    room already has did not happen.
    """
    from app.db.models.internalization_room import IRTake

    async def _database_goes_away(*_: Any, **__: Any) -> bytes:
        """Leave the session holding something it will refuse to write.

        A row short of a column the table requires, so the write the room does next — keeping
        the rebuilt passage — is the statement that fails. Which is where a database failure
        during a rebuilding actually lands.
        """
        db_session.add(
            IRTake(
                session_id=session_id,
                device_id=DEVICE,
                pericope=None,
                kind=IRTakeKind.ENSAIO,
                scope="uma-linha-que-o-banco-recusa",
                storage_key="nao-importa",
                size_bytes=1,
                sha256="0" * 64,
                crc32c="AAAAAAA=",
                content_type="audio/mp4",
            )
        )
        return b"nao chega a ser guardado"

    session_id, take_id = await _three_stretches_over_one_recording(client)
    middle = (await _units(client, session_id))[1]
    corrected = await _rehearse(client, session_id, CORRECTED_AUDIO, "trecho-2")
    rebuilder.calls.clear()

    with caplog.at_level(logging.WARNING):
        import app.services.internalization_room.compose as under_test

        original = under_test.compose_passage
        under_test.compose_passage = _database_goes_away
        try:
            answered = await _replace(
                client,
                session_id,
                middle["segment_id"],
                take_id=corrected,
                starts_ms=0,
                ends_ms=CORRECTED_MS,
            )
        finally:
            under_test.compose_passage = original

    assert answered.status_code == 200, answered.text
    assert answered.json()["composed_take_id"] is None
    assert _spans(await _units(client, session_id)) == [
        (take_id, 0, 5000),
        (corrected, 0, CORRECTED_MS),
        (take_id, 12000, 20000),
    ], "a correção ficou de pé"
    assert [
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.WARNING and session_id in record.getMessage()
    ], "e o aviso saiu"


# ---------------------------------------------------------------------------
# 9. The real encoder, once
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="needs ffmpeg and ffprobe on the PATH",
)
async def test_the_rebuilt_passage_is_audio_somebody_can_play() -> None:
    """The one case with a real encoder: what comes out has to be playable audio.

    Three tones make a passage of seven seconds; the middle three seconds are replaced by a
    tone of four. The result has to *decode*, and to last eight seconds — the passage grew by
    exactly the second the correction added. Tolerance because the encoder pads its last frame,
    not because the arithmetic is uncertain.
    """
    compose_module = importlib.import_module("app.services.internalization_room.compose")

    with tempfile.TemporaryDirectory() as workspace:
        room = Path(workspace)
        passage = _tones(room, [(440, 2), (660, 3), (880, 2)])
        correction = _tones(room, [(330, 4)])

        rebuilt = await compose_module.compose_passage(
            passage, correction, starts_ms=2000, ends_ms=5000
        )

        played = room / "refeita.m4a"
        played.write_bytes(rebuilt)
        assert abs(_seconds(played) - 8.0) < 0.1
        assert _codec(played) == "aac"

        opening = await compose_module.compose_passage(
            passage, correction, starts_ms=0, ends_ms=2000
        )
        first = room / "refeita-do-comeco.m4a"
        first.write_bytes(opening)
        assert abs(_seconds(first) - 9.0) < 0.1, (
            "corrigir o primeiro trecho deixa a cabeça vazia, e o encoder aceita"
        )

        trimmed = await compose_module.compose_passage(
            passage,
            correction,
            starts_ms=2000,
            ends_ms=5000,
            corrected_starts_ms=500,
            corrected_ends_ms=3500,
        )
        aparada = room / "refeita-com-fatia.m4a"
        aparada.write_bytes(trimmed)
        assert abs(_seconds(aparada) - 7.0) < 0.1, (
            "entra a fatia endereçada da correção, e não o arquivo em que ela está"
        )


def _tones(room: Path, parts: list[tuple[int, int]]) -> bytes:
    """One recording made of tones, as bytes — a passage, or one stretch of one."""
    pieces = []
    for index, (hertz, seconds) in enumerate(parts):
        piece = room / f"tom-{hertz}-{index}.wav"
        _ffmpeg(
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency={hertz}:duration={seconds}:sample_rate=44100",
            "-ac",
            "1",
            str(piece),
        )
        pieces.append(piece)

    listing = room / f"lista-{len(parts)}-{parts[0][0]}.txt"
    listing.write_text("".join(f"file '{piece}'\n" for piece in pieces))
    whole = room / f"inteiro-{parts[0][0]}.wav"
    _ffmpeg("-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(whole))
    return whole.read_bytes()


def _ffmpeg(*arguments: str) -> None:
    done = subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", *arguments], capture_output=True, timeout=120
    )
    assert done.returncode == 0, done.stderr.decode()


def _probe(path: Path, entries: str) -> str:
    done = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", entries, "-of", "csv=p=0", str(path)],
        capture_output=True,
        timeout=120,
    )
    assert done.returncode == 0, done.stderr.decode()
    return done.stdout.decode().strip()


def _seconds(path: Path) -> float:
    return float(_probe(path, "format=duration").splitlines()[0])


def _codec(path: Path) -> str:
    return _probe(path, "stream=codec_name").splitlines()[0]
