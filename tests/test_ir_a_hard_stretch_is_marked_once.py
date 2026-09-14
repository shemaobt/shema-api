"""ENG-869 — the third telling of one stretch makes it a hard stretch, marked once.

The count of tellings was one integer per session, so three tellings spread over three
different stretches raised the same warning as three tellings of one — and the warning was
raised again on the fourth and the fifth, each time erasing the record that a facilitator had
already walked to the room. Then the next turn that landed cleared the halt itself, so by the
time the consultant opened the session there was nothing left to read.

The count moves onto the stretch and follows its chain of replacements; the crossing writes a
row of its own that nothing clears. What the room does with it is unchanged: a warning, never
a cap — Marcia's ruling of 08/09.

Nothing on the voice path may read either. The team never hears that the room counted.
"""

from __future__ import annotations

import base64
from typing import Any

import httpx
import pytest
from google_crc32c import Checksum
from httpx import ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ProjectRole
from app.db.models.internalization_room import (
    IRHardStretch,
    IRPromptKey,
    IRSegment,
    IRSession,
    IRSessionStatus,
    IRTakeKind,
)
from app.services.internalization_room import sessions as room
from app.services.internalization_room.sessions import RETELLS_BEFORE_A_WARNING
from app.services.platform.storage import StoredObject
from app.services.platform.tts import SynthesizedSpeech
from tests.baker import (
    grant_facilitator_app_role,
    make_language,
    make_project,
    make_project_user_access,
    make_user,
)

IR = "/api/internalization-room"
DESK = "/api/facilitator/teams"
ROOM_KEY = "sala-de-teste"
DEVICE = "tablet-da-equipe-1"
P = "P01"
AUDIO = b"a equipe explicou este trecho em portugues"
WARNING = "warning"
BLOCKING = "blocking"

#: The stretches the helpers below tell, as slices of the one rehearsal recording.
SLICES = [(0, 9000), (9000, 18000), (18000, 27000)]


class _MemoryStore:
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


async def _voice(text: str, **_: Any) -> tuple[SynthesizedSpeech, bool]:
    entry = SynthesizedSpeech(
        audio=b"audio",
        mime_type="audio/mpeg",
        etag="e",
        cached=False,
        key=f"tts/voice/m/f/{abs(hash(text))}.mp3",
    )
    return entry, False


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    """The room and the Desk on one app: a mark is written on one side and read on the other.

    `client.said` queues what the transcriber will answer, one entry per capture. An entry of
    `""` is the outage the room cannot tell from silence.
    """
    from fastapi import FastAPI

    from app.api.facilitator.teams import facilitator_teams_router
    from app.api.internalization_room import back_translation as bt_api
    from app.api.internalization_room import router as room_router
    from app.api.internalization_room import segments as segments_api
    from app.api.internalization_room import sessions as sessions_api
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers
    from app.services.internalization_room import takes as takes_service

    monkeypatch.setattr(get_settings(), "internalization_room_api_key", ROOM_KEY, raising=False)
    monkeypatch.setattr(sessions_api.room, "synthesize_facilitator_speech", _voice)
    monkeypatch.setattr(bt_api.room, "synthesize_facilitator_speech", _voice)

    said: list[str] = []

    async def _transcribe(*_: Any, **__: Any) -> str:
        return said.pop(0) if said else "algo que a equipe contou"

    monkeypatch.setattr(bt_api, "heard", _transcribe)
    monkeypatch.setattr(segments_api, "heard", _transcribe)
    bucket = _MemoryStore()
    monkeypatch.setattr(takes_service, "_store", lambda *_, **__: bucket)

    test_app = FastAPI()
    test_app.include_router(room_router, prefix=IR)
    test_app.include_router(facilitator_teams_router, prefix=DESK)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        c.said = said  # type: ignore[attr-defined]
        yield c


@pytest.fixture()
def the_room_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    """An analyst that finds nothing and a Speaker that says so, so `terminei` can land.

    No assertion here is about either: they stand in for the two model calls a press has to
    reach through, and the case that *is* about them is the byte-identical one below.
    """
    from app.services.internalization_room import verdict_round
    from app.services.internalization_room.back_translation import BtAnalysis
    from app.services.internalization_room.validated_turn import TurnOutcome

    async def _analyst(**_: Any) -> BtAnalysis:
        return BtAnalysis(findings=[])

    async def _speaker(**_: Any) -> TurnOutcome:
        return TurnOutcome(speech="a passagem está conferida", transcript="")

    monkeypatch.setattr(verdict_round, "analyse_telling_back", _analyst)
    monkeypatch.setattr(verdict_round, "run_verdict_turn", _speaker)


class Facilitator:
    def __init__(self, user_id: str, team_id: str, headers: dict[str, str]) -> None:
        self.id = user_id
        self.team_id = team_id
        self.headers = headers


@pytest.fixture()
async def facilitator(db_session: AsyncSession) -> Facilitator:
    from app.services.auth.issue_tokens import issue_tokens

    user = await make_user(db_session, email="ana@example.com")
    language = await make_language(db_session, name="Lingua P", code="lgp")
    project = await make_project(db_session, language.id, name="Equipe P")
    await make_project_user_access(db_session, project.id, user.id, role=ProjectRole.FACILITATOR)
    await grant_facilitator_app_role(db_session, user.id)
    access, _refresh = await issue_tokens(db_session, user)
    return Facilitator(user.id, project.id, {"Authorization": f"Bearer {access}"})


# --- what the team does ---------------------------------------------------------------


async def _a_session(db: AsyncSession, *, team_id: str | None = None) -> str:
    """A session, named by its id: the reads below expire the identity map."""
    session = await room.create_session(db, pericope=P, project_id=team_id)
    return str(session.id)


async def _rehearse(client: httpx.AsyncClient, session_id: str) -> str:
    kept = await client.post(
        f"{IR}/sessions/{session_id}/takes",
        headers={"X-Room-Key": ROOM_KEY, "X-Room-Device": DEVICE},
        data={"kind": IRTakeKind.ENSAIO.value, "scope": P},
        files={"file": ("ensaio.m4a", b"a equipe ensaiou a passagem inteira", "audio/mp4")},
    )
    assert kept.status_code == 200, kept.text
    return str(kept.json()["take_id"])


async def _tell(
    client: httpx.AsyncClient,
    session_id: str,
    take_id: str,
    stretch: int,
    *,
    again: bool = False,
    saying: str | None = None,
) -> httpx.Response:
    """Tell stretch `stretch` (1-based) back, as a first telling or as one more.

    `saying=None` is the transcriber coming back with nothing, which is the shape of an
    outage and the case Marcia named by name.
    """
    starts, ends = SLICES[stretch - 1]
    client.said.append(saying if saying is not None else "")  # type: ignore[attr-defined]
    data = {"take_id": take_id, "starts_ms": str(starts), "ends_ms": str(ends)}
    if again:
        data["retelling"] = "true"
    return await client.post(
        f"{IR}/sessions/{session_id}/back-translation/chunks",
        headers={"X-Room-Key": ROOM_KEY, "X-Room-Device": DEVICE},
        data=data,
        files={"file": ("trecho.m4a", AUDIO, "audio/mp4")},
    )


async def _told(client: httpx.AsyncClient, session_id: str, take_id: str, how_many: int) -> None:
    """A first telling of the first `how_many` stretches, each with words in it."""
    for stretch in range(1, how_many + 1):
        answered = await _tell(client, session_id, take_id, stretch, saying=f"o trecho {stretch}")
        assert answered.status_code == 200, answered.text


async def _units(client: httpx.AsyncClient, session_id: str) -> list[dict[str, Any]]:
    state = await client.get(f"{IR}/sessions/{session_id}", headers={"X-Room-Key": ROOM_KEY})
    assert state.status_code == 200, state.text
    return list(state.json()["back_translation"]["segments"])


# --- what the room and the Desk say -----------------------------------------------------


#: The routes wrote through this same session, so an instance left unexpired would answer from
#: the identity map and an assertion could pass without anything having reached the column.
#: `populate_existing` refreshes the rows this read returns and leaves every other one alone,
#: which `expire_all` does not: expiring the session object mid-test makes the next read of its
#: id a query from outside the async context.
FROM_THE_DATABASE = {"populate_existing": True}


async def _row(db: AsyncSession, session_id: str) -> IRSession:
    result = await db.execute(
        select(IRSession).where(IRSession.id == session_id).execution_options(**FROM_THE_DATABASE)
    )
    return result.scalar_one()


async def _current(db: AsyncSession, session_id: str) -> list[IRSegment]:
    result = await db.execute(
        select(IRSegment)
        .where(IRSegment.session_id == session_id, IRSegment.superseded_at.is_(None))
        .order_by(IRSegment.ordinal)
        .execution_options(**FROM_THE_DATABASE)
    )
    return list(result.scalars().all())


async def _marks(db: AsyncSession, session_id: str) -> list[IRHardStretch]:
    result = await db.execute(
        select(IRHardStretch)
        .where(IRHardStretch.session_id == session_id)
        .order_by(IRHardStretch.crossed_at, IRHardStretch.segment_id)
        .execution_options(**FROM_THE_DATABASE)
    )
    return list(result.scalars().all())


async def _queued(
    client: httpx.AsyncClient, who: Facilitator, session_id: str
) -> dict[str, Any] | None:
    listed = await client.get(f"{IR}/facilitator/sessions", headers=who.headers)
    assert listed.status_code == 200, listed.text
    return next((row for row in listed.json()["sessions"] if row["session_id"] == session_id), None)


async def _attend(client: httpx.AsyncClient, session_id: str, who: Facilitator) -> httpx.Response:
    return await client.post(
        f"{IR}/facilitator/sessions/{session_id}/attended", headers=who.headers
    )


# ---------------------------------------------------------------------------
# 1. The third telling asks for a person, and only the third
# ---------------------------------------------------------------------------


async def test_the_third_telling_of_one_stretch_asks_for_a_person_once(
    client: httpx.AsyncClient, db_session: AsyncSession, facilitator: Facilitator
) -> None:
    """The defect this ticket is about, end to end.

    The fourth telling used to raise the ask again, and `mark_needs_person` clears the stamps
    on every call — so the room deleted the record that somebody had already walked over.
    """
    session_id = await _a_session(db_session, team_id=facilitator.team_id)
    take_id = await _rehearse(client, session_id)
    await _told(client, session_id, take_id, 2)

    second = await _tell(client, session_id, take_id, 2, again=True, saying="de novo")
    assert second.status_code == 200, second.text
    assert second.json()["needs_person"] is False, "duas contagens não fazem um trecho difícil"

    third = await _tell(client, session_id, take_id, 2, again=True, saying="e outra vez")
    assert third.status_code == 200, third.text
    assert third.json()["needs_person"] is True
    halted = await _row(db_session, session_id)
    assert halted.status is IRSessionStatus.NEEDS_PERSON
    assert halted.halt_kind == WARNING

    marked = await _attend(client, session_id, facilitator)
    assert marked.status_code == 200, marked.text
    attended = await _row(db_session, session_id)
    stamps = (attended.attended_at, attended.attended_by, attended.person_arrived_at)
    assert stamps[0] is not None and stamps[1] == facilitator.id

    for saying in ("uma quarta vez", "uma quinta vez"):
        more = await _tell(client, session_id, take_id, 2, again=True, saying=saying)
        assert more.status_code == 200, more.text
        assert more.json()["needs_person"] is False, (
            "o pedido é uma vez por trecho; repetido, apaga a visita que já aconteceu"
        )

    after = await _row(db_session, session_id)
    assert (after.attended_at, after.attended_by, after.person_arrived_at) == stamps


# ---------------------------------------------------------------------------
# 2. A second hard stretch asks again
# ---------------------------------------------------------------------------


async def test_a_second_hard_stretch_asks_again(
    client: httpx.AsyncClient, db_session: AsyncSession, facilitator: Facilitator
) -> None:
    """Once per stretch, not once per session: a different stretch is a different ask."""
    session_id = await _a_session(db_session, team_id=facilitator.team_id)
    take_id = await _rehearse(client, session_id)
    await _told(client, session_id, take_id, 2)

    for saying in ("de novo", "e outra vez"):
        await _tell(client, session_id, take_id, 2, again=True, saying=saying)
    assert (await _attend(client, session_id, facilitator)).status_code == 200

    await _tell(client, session_id, take_id, 1, again=True, saying="o primeiro de novo")
    crossed = await _tell(client, session_id, take_id, 1, again=True, saying="o primeiro outra vez")

    assert crossed.status_code == 200, crossed.text
    assert crossed.json()["needs_person"] is True
    assert (await _row(db_session, session_id)).status is IRSessionStatus.NEEDS_PERSON

    marks = await _marks(db_session, session_id)
    assert len(marks) == 2, "um trecho difícil por trecho, e os dois ficam"
    assert [mark.tellings for mark in marks] == [RETELLS_BEFORE_A_WARNING] * 2
    assert len({mark.segment_id for mark in marks}) == 2


# ---------------------------------------------------------------------------
# 3. Nothing that follows clears the mark
# ---------------------------------------------------------------------------


async def test_the_mark_survives_everything_that_follows(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    facilitator: Facilitator,
    the_room_answers: None,
) -> None:
    """Marcia's third condition: it belongs in the record, with the tellings themselves.

    `append_exchange` sets `IN_PROGRESS` on any landing turn, which is what used to erase
    the notice — not `terminei`, but the next thing the team said, whatever it was.
    """
    session_id = await _a_session(db_session, team_id=facilitator.team_id)
    take_id = await _rehearse(client, session_id)
    await _told(client, session_id, take_id, 2)
    for saying in ("de novo", "e outra vez"):
        await _tell(client, session_id, take_id, 2, again=True, saying=saying)

    async def _standing() -> list[tuple[str, int, Any]]:
        return [
            (mark.segment_id, mark.tellings, mark.crossed_at)
            for mark in await _marks(db_session, session_id)
        ]

    kept = await _standing()
    assert len(kept) == 1

    landed = await room.append_exchange(
        db_session,
        await _row(db_session, session_id),
        team_utterance="voltamos",
        guide_response="que bom",
    )
    assert landed.status is IRSessionStatus.IN_PROGRESS
    assert await _standing() == kept, "o próximo turno que pousa apagava a marca"

    finished = await client.post(
        f"{IR}/sessions/{session_id}/back-translation/finish",
        headers={"X-Room-Key": ROOM_KEY},
        json={},
    )
    assert finished.status_code == 200, finished.text
    assert await _standing() == kept, "e 'terminei' também"

    assert (await _attend(client, session_id, facilitator)).status_code == 200
    assert await _standing() == kept

    restarted = await client.post(
        f"{IR}/sessions/{session_id}/back-translation/restart",
        headers={"X-Room-Key": ROOM_KEY},
    )
    assert restarted.status_code == 200, restarted.text
    assert await _standing() == kept, (
        "recomeçar o contado de volta aposenta todo trecho; a marca não é parte dele"
    )


# ---------------------------------------------------------------------------
# 4. A blocking halt after a warning still clears the stamps
# ---------------------------------------------------------------------------


async def test_a_blocking_halt_after_a_warning_still_clears_the_stamps(
    client: httpx.AsyncClient, db_session: AsyncSession, facilitator: Facilitator
) -> None:
    """The guard on the change: "a new ask is an unattended ask" stays true for a real halt.

    Marking once per stretch must not turn into marking once per session, which would leave a
    facilitator reading a stamp that answered a halt nobody has been to.
    """
    session_id = await _a_session(db_session, team_id=facilitator.team_id)
    take_id = await _rehearse(client, session_id)
    await _told(client, session_id, take_id, 2)
    for saying in ("de novo", "e outra vez"):
        await _tell(client, session_id, take_id, 2, again=True, saying=saying)
    assert (await _attend(client, session_id, facilitator)).status_code == 200
    attended = await _row(db_session, session_id)
    assert attended.attended_at is not None

    stopped = await client.post(
        f"{IR}/sessions/{session_id}/needs-person", headers={"X-Room-Key": ROOM_KEY}
    )
    assert stopped.status_code == 200, stopped.text

    blocked = await _row(db_session, session_id)
    assert blocked.halt_kind == BLOCKING
    assert blocked.attended_at is None
    assert blocked.attended_by is None
    assert blocked.person_arrived_at is None


# ---------------------------------------------------------------------------
# 5. The facilitator reads the marks; the tablet does not
# ---------------------------------------------------------------------------


async def test_the_facilitator_queue_lists_the_marks_and_the_tablet_does_not(
    client: httpx.AsyncClient, db_session: AsyncSession, facilitator: Facilitator
) -> None:
    """Facilitator-only, explicitly. The team never hears that the room counted."""
    session_id = await _a_session(db_session, team_id=facilitator.team_id)
    take_id = await _rehearse(client, session_id)
    await _told(client, session_id, take_id, 2)
    first_of_the_chain = (await _current(db_session, session_id))[1].id
    for saying in ("de novo", "e outra vez"):
        await _tell(client, session_id, take_id, 2, again=True, saying=saying)

    row = await _queued(client, facilitator, session_id)
    assert row is not None
    assert len(row["hard_stretches"]) == 1
    listed = row["hard_stretches"][0]
    assert listed["segment_id"] == first_of_the_chain, (
        "a marca nomeia a primeira linha da corrente, que é o trecho e não a versão"
    )
    assert listed["tellings"] == RETELLS_BEFORE_A_WARNING
    assert listed["crossed_at"]

    state = await client.get(f"{IR}/sessions/{session_id}", headers={"X-Room-Key": ROOM_KEY})
    assert state.status_code == 200, state.text
    body = state.json()
    assert "hard_stretches" not in body
    assert "hard_stretches" not in body["back_translation"]
    assert "retells" not in body["back_translation"], (
        "a contagem por sessão sai da leitura do tablet junto com o contador"
    )


# ---------------------------------------------------------------------------
# 6. Nothing on the voice path reads the count
# ---------------------------------------------------------------------------


async def test_the_voice_path_is_byte_identical_with_and_without_a_mark(
    client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Twins: two sessions told exactly the same, one of them carrying a mark.

    Recorded as what the model actually receives — the rendered blocks and the scalars —
    rather than as the row objects, because the row objects are what may not leak.
    """
    from app.api.internalization_room import back_translation as bt_api
    from app.services.internalization_room import verdict_round
    from app.services.internalization_room.back_translation import BtAnalysis
    from app.services.internalization_room.validated_turn import TurnOutcome

    readings: list[dict[str, Any]] = []
    verdicts: list[dict[str, Any]] = []

    async def _analyst(**kwargs: Any) -> BtAnalysis:
        readings.append(
            {**kwargs, "segments": bt_api.room.segments_block(kwargs["segments"]), "session_id": ""}
        )
        return BtAnalysis(findings=[])

    async def _speaker(**kwargs: Any) -> TurnOutcome:
        verdicts.append({**kwargs, "session_id": ""})
        return TurnOutcome(speech="a passagem está conferida", transcript="")

    monkeypatch.setattr(verdict_round, "analyse_telling_back", _analyst)
    monkeypatch.setattr(verdict_round, "run_verdict_turn", _speaker)

    async def _a_twin(*, with_a_mark: bool) -> dict[str, Any]:
        session_id = await _a_session(db_session)
        take_id = await _rehearse(client, session_id)
        await _told(client, session_id, take_id, 2)
        if with_a_mark:
            # Word for word what stretch 2 already said, so the only difference between the
            # twins is the mark itself and never the telling-back the analyst reads.
            for _ in range(2):
                await _tell(client, session_id, take_id, 2, again=True, saying="o trecho 2")
            assert await _marks(db_session, session_id), "o gêmeo marcado não foi marcado"
        answered = await client.post(
            f"{IR}/sessions/{session_id}/back-translation/finish",
            headers={"X-Room-Key": ROOM_KEY},
            json={},
        )
        assert answered.status_code == 200, answered.text
        return answered.json()

    plain = await _a_twin(with_a_mark=False)
    marked = await _a_twin(with_a_mark=True)

    assert len(readings) == 2 and len(verdicts) == 2
    assert readings[0] == readings[1], "a contagem chegou ao analista"
    assert verdicts[0] == verdicts[1], "a contagem chegou ao Falante"
    assert plain["fixed_line"] == marked["fixed_line"]
    assert plain["checked"] == marked["checked"]


async def test_the_three_prompts_are_byte_identical_with_and_without_the_count(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The acceptance criterion, at the only place it can be settled: what reaches the model.

    The twin above holds the room's own seams still and compares what the route hands them.
    This one goes a layer down and compares the bytes: the analyst and the correction check
    both call `call_agent` from the telling-back service, so one recorder catches the two
    prompts the criterion names beside the Speaker's.

    Told twice against the same two rows, once with the count at one and once at the number
    that makes a hard stretch. Nothing about the crossing may reach either prompt.
    """
    from app.services.internalization_room import back_translation as service
    from app.services.internalization_room.back_translation import Finding, FindingKind
    from app.services.internalization_room.prompts import get_prompt_text
    from app.services.internalization_room.segments import capture_segment

    said: list[tuple[str, str]] = []

    async def _recorder(*, system_prompt: str, user_content: str, **_: Any) -> str:
        said.append((system_prompt, user_content))
        return '{"evidence_sufficient": true, "findings": []}'

    monkeypatch.setattr(service, "call_agent", _recorder)

    session = await room.create_session(db_session, pericope=P)
    earlier = await capture_segment(
        db_session,
        session,
        take_id="ensaio-1",
        starts_ms=0,
        ends_ms=9000,
        bridge_take_id="retro-1",
        transcript="Noemi voltou para Belém",
    )
    corrected = await capture_segment(
        db_session,
        session,
        take_id="ensaio-1",
        starts_ms=9000,
        ends_ms=18000,
        bridge_take_id="retro-2",
        transcript="e Rute foi com ela",
    )
    finding = Finding(kind=FindingKind.MISSING, note="a colheita da cevada", segment_id=earlier.id)

    async def _both_prompts() -> list[tuple[str, str]]:
        said.clear()
        await service.analyse_telling_back(
            segments=[earlier, corrected],
            scope=P,
            pericope_num=P,
            analyst_prompt=get_prompt_text(IRPromptKey.BT_ANALYST),
        )
        await service.verify_correction(
            findings=[finding],
            earlier=earlier,
            corrected=corrected,
            chunk=1,
            scope=P,
            pericope_num=P,
            correction_prompt=get_prompt_text(IRPromptKey.BT_CORRECTION),
        )
        return list(said)

    plain = await _both_prompts()
    assert len(plain) == 2, "o analista e a verificação da correção, um prompt cada"

    earlier.tellings = RETELLS_BEFORE_A_WARNING
    corrected.tellings = RETELLS_BEFORE_A_WARNING
    await db_session.commit()

    assert await _both_prompts() == plain, (
        "a contagem chegou ao modelo: nada sobre um trecho difícil pode mudar o que ele lê"
    )


async def test_a_stretch_left_at_the_number_with_no_mark_is_still_marked(
    db_session: AsyncSession,
) -> None:
    """The crossing has to be recoverable, because the count and the mark have come apart.

    The captured path wrote the row in one transaction and the mark in the next, so a failure
    between them left a stretch standing at the number carrying no mark. ENG-886 closed that
    door — the row, the state and the mark are one transaction now — and it does not reopen the
    stretches it already left behind. A gate reading exact equality would never mark those,
    because the count only ever grows. The gate asks the table instead, so the next telling
    finds the count past the number, finds no mark, and writes it.
    """
    from app.services.internalization_room.hard_stretches import note_a_hard_stretch
    from app.services.internalization_room.segments import capture_segment

    session = await room.create_session(db_session, pericope=P)
    session_id = str(session.id)
    told = await capture_segment(
        db_session,
        session,
        take_id="ensaio-1",
        starts_ms=0,
        ends_ms=9000,
        bridge_take_id="retro-1",
        transcript="o trecho",
    )

    told.tellings = RETELLS_BEFORE_A_WARNING
    await db_session.commit()
    assert await note_a_hard_stretch(db_session, session, told) is True
    assert len(await _marks(db_session, session_id)) == 1

    told.tellings = RETELLS_BEFORE_A_WARNING + 1
    await db_session.commit()

    assert await note_a_hard_stretch(db_session, session, told) is False, (
        "a marca é o que mantém o pedido em um; a contagem só cresce"
    )
    assert len(await _marks(db_session, session_id)) == 1


async def test_a_count_left_past_the_number_by_a_lost_mark_is_recovered(
    db_session: AsyncSession,
) -> None:
    """The other half: past the number and never marked at all, the next telling marks."""
    from app.services.internalization_room.hard_stretches import note_a_hard_stretch
    from app.services.internalization_room.segments import capture_segment

    session = await room.create_session(db_session, pericope=P)
    session_id = str(session.id)
    told = await capture_segment(
        db_session,
        session,
        take_id="ensaio-1",
        starts_ms=0,
        ends_ms=9000,
        bridge_take_id="retro-1",
        transcript="o trecho",
    )
    told.tellings = RETELLS_BEFORE_A_WARNING + 2
    await db_session.commit()

    assert await note_a_hard_stretch(db_session, session, told) is True
    marks = await _marks(db_session, session_id)
    assert [mark.tellings for mark in marks] == [RETELLS_BEFORE_A_WARNING + 2], (
        "a marca guarda a contagem do momento em que foi escrita"
    )


async def test_an_empty_re_recording_is_refused_on_a_stretch_that_no_longer_counts(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """A retry that lands on a retired row must not spend a telling on it.

    The captured branch is refused by `capture_segment`; counting had no such guard, so an
    unheard retry counted on a row nothing can ever replace — and could mark it hard.
    """
    session_id = await _a_session(db_session)
    take_id = await _rehearse(client, session_id)
    await _told(client, session_id, take_id, 1)
    retired = (await _units(client, session_id))[0]
    await _tell(client, session_id, take_id, 1, again=True, saying="e de novo")

    client.said.append("")  # type: ignore[attr-defined]
    refused = await client.post(
        f"{IR}/sessions/{session_id}/segments/{retired['segment_id']}/replace",
        headers={"X-Room-Key": ROOM_KEY, "X-Room-Device": DEVICE},
        data={
            "take_id": retired["take_id"],
            "starts_ms": str(retired["starts_ms"]),
            "ends_ms": str(retired["ends_ms"]),
        },
        files={"file": ("trecho.m4a", AUDIO, "audio/mp4")},
    )

    assert refused.status_code == 400, refused.text
    assert [one.tellings for one in await _current(db_session, session_id)] == [2], (
        "a tentativa recusada não pode contar na linha que está de pé"
    )
    assert await _marks(db_session, session_id) == []


async def test_an_empty_re_recording_is_refused_on_a_divided_stretch(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """A divided parent is not a unit, so nothing counts on it and nothing marks it."""
    session_id = await _a_session(db_session)
    take_id = await _rehearse(client, session_id)
    await _told(client, session_id, take_id, 1)
    parent = (await _units(client, session_id))[0]
    divided = await client.post(
        f"{IR}/sessions/{session_id}/segments/{parent['segment_id']}/divide",
        headers={"X-Room-Key": ROOM_KEY, "X-Room-Device": DEVICE},
        json={"at_ms": 4000},
    )
    assert divided.status_code == 200, divided.text

    client.said.append("")  # type: ignore[attr-defined]
    refused = await client.post(
        f"{IR}/sessions/{session_id}/segments/{parent['segment_id']}/replace",
        headers={"X-Room-Key": ROOM_KEY, "X-Room-Device": DEVICE},
        data={
            "take_id": parent["take_id"],
            "starts_ms": str(parent["starts_ms"]),
            "ends_ms": str(parent["ends_ms"]),
        },
        files={"file": ("trecho.m4a", AUDIO, "audio/mp4")},
    )

    assert refused.status_code == 400, refused.text
    db_session.expire_all()
    stood = await _current(db_session, session_id)
    assert [one.tellings for one in stood] == [1, 1, 1], "nem o pai nem os pedaços contaram"
    assert await _marks(db_session, session_id) == []


async def test_the_packet_carries_no_count_of_retells(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """The per-session counter left the packet with the field it came from.

    Consultant material does not travel to Refine, and this number never was any: it was the
    room's own bookkeeping, read by nobody on the other side.
    """
    from tests.test_ir_a_take_is_numbered_by_its_stretch import _ready_for_release

    session_id = await _a_session(db_session)
    take_id = await _rehearse(client, session_id)
    await _told(client, session_id, take_id, 3)

    packet = await _ready_for_release(db_session, await _row(db_session, session_id))

    assert "retells" not in packet["back_translation"]
    assert "retells" not in str(packet), "a contagem por sessão saiu do pacote inteiro"


# ---------------------------------------------------------------------------
# 7. Three tellings over three stretches raise nothing
# ---------------------------------------------------------------------------


async def test_three_retellings_over_three_stretches_raise_no_warning(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """The control that says the count is per stretch and not per session.

    This is the case the per-session counter got wrong in the other direction: a team working
    steadily through three different stretches was handed to a person having repeated nothing.
    """
    session_id = await _a_session(db_session)
    take_id = await _rehearse(client, session_id)
    await _told(client, session_id, take_id, 3)

    for stretch in (1, 2, 3):
        again = await _tell(
            client, session_id, take_id, stretch, again=True, saying=f"o trecho {stretch} de novo"
        )
        assert again.status_code == 200, again.text
        assert again.json()["needs_person"] is False
        assert (await _row(db_session, session_id)).status is not IRSessionStatus.NEEDS_PERSON

    assert await _marks(db_session, session_id) == []


# ---------------------------------------------------------------------------
# 8. A telling nobody could make out counts in place
# ---------------------------------------------------------------------------


async def test_an_empty_retelling_counts_in_place(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Marcia named this case: "either a hard stretch or the recognizer failing".

    Nothing is captured, so there is no new row to carry a count onto — the count goes onto
    the row that is standing, which is the stretch they were telling.
    """
    session_id = await _a_session(db_session)
    take_id = await _rehearse(client, session_id)
    await _told(client, session_id, take_id, 1)

    first = await _tell(client, session_id, take_id, 1, again=True)
    assert first.status_code == 200, first.text
    assert first.json()["captured"] is False
    assert first.json()["needs_person"] is False

    second = await _tell(client, session_id, take_id, 1, again=True)
    assert second.status_code == 200, second.text
    assert second.json()["captured"] is False
    assert second.json()["needs_person"] is True

    standing = await _current(db_session, session_id)
    assert len(standing) == 1, "uma tentativa que não foi entendida não vira trecho"
    assert standing[0].tellings == RETELLS_BEFORE_A_WARNING
    assert [mark.segment_id for mark in await _marks(db_session, session_id)] == [standing[0].id]


async def test_an_empty_re_recording_counts_in_place(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """The same rule on the route the team corrects by."""
    session_id = await _a_session(db_session)
    take_id = await _rehearse(client, session_id)
    await _told(client, session_id, take_id, 1)
    stretch = (await _units(client, session_id))[0]

    for _ in range(2):
        client.said.append("")  # type: ignore[attr-defined]
        answered = await client.post(
            f"{IR}/sessions/{session_id}/segments/{stretch['segment_id']}/replace",
            headers={"X-Room-Key": ROOM_KEY, "X-Room-Device": DEVICE},
            data={
                "take_id": stretch["take_id"],
                "starts_ms": str(stretch["starts_ms"]),
                "ends_ms": str(stretch["ends_ms"]),
            },
            files={"file": ("trecho.m4a", AUDIO, "audio/mp4")},
        )
        assert answered.status_code == 200, answered.text
        assert answered.json()["captured"] is False

    assert answered.json()["needs_person"] is True
    standing = await _current(db_session, session_id)
    assert [one.tellings for one in standing] == [RETELLS_BEFORE_A_WARNING]
    assert len(await _marks(db_session, session_id)) == 1


# ---------------------------------------------------------------------------
# 9. A retelling supersedes the stretch it retells
# ---------------------------------------------------------------------------


async def test_a_retelling_supersedes_the_stretch_it_retells(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """The decision of 2026-09-10, and what makes a chain for the count to live on.

    The chunks route wrote an unchained pass-2 row at the next position, so the stretch the team
    had just told again appeared beside itself and the stretch it answered stayed waiting.
    """
    session_id = await _a_session(db_session)
    take_id = await _rehearse(client, session_id)
    await _told(client, session_id, take_id, 2)
    before = await _current(db_session, session_id)
    replaced = before[0]

    again = await _tell(client, session_id, take_id, 1, again=True, saying="o primeiro de novo")

    assert again.status_code == 200, again.text
    assert again.json()["chunks"] == 2, "contar de novo não acrescenta um trecho à passagem"
    standing = await _current(db_session, session_id)
    assert len(standing) == 2
    current = standing[0]
    assert current.id != replaced.id
    assert current.ordinal == replaced.ordinal
    assert current.pass_number == 2
    assert current.tellings == 2

    retired = (
        await db_session.execute(
            select(IRSegment)
            .where(IRSegment.id == replaced.id)
            .execution_options(**FROM_THE_DATABASE)
        )
    ).scalar_one()
    assert retired.superseded_at is not None
    assert retired.superseded_by_id == current.id


async def test_re_recording_the_mother_tongue_is_not_a_telling(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """A new recording under a stretch carries no words, so it counts nothing.

    The team records the stretch again and then tells it back, which is two calls and one
    telling. Counted on the supersession rather than on the telling, that pair would reach
    three on the team's second telling and ask for a person a whole telling early.
    """
    session_id = await _a_session(db_session)
    take_id = await _rehearse(client, session_id)
    await _told(client, session_id, take_id, 1)
    stretch = (await _units(client, session_id))[0]

    fresh = await client.post(
        f"{IR}/sessions/{session_id}/takes",
        headers={"X-Room-Key": ROOM_KEY, "X-Room-Device": DEVICE},
        data={"kind": IRTakeKind.ENSAIO.value, "scope": P},
        files={"file": ("de-novo.m4a", b"a equipe gravou o trecho de novo", "audio/mp4")},
    )
    assert fresh.status_code == 200, fresh.text
    fresh_take = fresh.json()["take_id"]

    rerecorded = await client.post(
        f"{IR}/sessions/{session_id}/segments/{stretch['segment_id']}/replace",
        headers={"X-Room-Key": ROOM_KEY, "X-Room-Device": DEVICE},
        data={"take_id": fresh_take, "starts_ms": "0", "ends_ms": "9000"},
    )
    assert rerecorded.status_code == 200, rerecorded.text
    waiting = await _current(db_session, session_id)
    assert [one.tellings for one in waiting] == [1], (
        "a gravação nova não é uma contagem: ninguém contou nada nela"
    )

    client.said.append("o trecho contado sobre a gravação nova")  # type: ignore[attr-defined]
    retold = await client.post(
        f"{IR}/sessions/{session_id}/segments/{waiting[0].id}/replace",
        headers={"X-Room-Key": ROOM_KEY, "X-Room-Device": DEVICE},
        data={"take_id": fresh_take, "starts_ms": "0", "ends_ms": "9000"},
        files={"file": ("trecho.m4a", AUDIO, "audio/mp4")},
    )

    assert retold.status_code == 200, retold.text
    assert retold.json()["needs_person"] is False
    assert [one.tellings for one in await _current(db_session, session_id)] == [2]
    assert await _marks(db_session, session_id) == []


async def test_a_chunk_over_a_divided_stretchs_slice_is_a_first_telling(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """A stretch that was divided is no longer a unit, so nothing retells it.

    Looked up among every current row rather than among the leaves, the chunk would find the
    divided parent and `capture_segment` would refuse it — a refusal where the room used to
    take the team's work.
    """
    session_id = await _a_session(db_session)
    take_id = await _rehearse(client, session_id)
    await _told(client, session_id, take_id, 1)
    parent = (await _units(client, session_id))[0]

    divided = await client.post(
        f"{IR}/sessions/{session_id}/segments/{parent['segment_id']}/divide",
        headers={"X-Room-Key": ROOM_KEY, "X-Room-Device": DEVICE},
        json={"at_ms": 4000},
    )
    assert divided.status_code == 200, divided.text

    over_the_parent = await _tell(
        client, session_id, take_id, 1, again=True, saying="sobre a fatia inteira"
    )

    assert over_the_parent.status_code == 200, over_the_parent.text
    assert over_the_parent.json()["captured"] is True
    born = [one for one in await _current(db_session, session_id) if one.parent_id is None]
    assert [one.tellings for one in born] == [1, 1], (
        "nada foi substituído, então a fatia inteira é uma stretch que ninguém contou ainda"
    )
    assert born[-1].ordinal == 2, "e ela toma a posição seguinte, como qualquer primeira contagem"
