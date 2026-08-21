"""ENG-447 — the three things a raised-hand card shows that the question did not carry.

The Desk draws a card with the element the question is about, how long the recording runs,
and what was said. The model carried none of them: the app knew which bead the hand went up
on and had nowhere to put it, and nothing measured or read the audio.

Two of the three are allowed to be missing, and for different reasons. `element_key` is
missing on every row written before this and on every app that has not shipped ENG-456, so a
card without one is the common case rather than an error. `transcript` and `duration_ms` are
missing when a machine that is not this one failed — and the question outliving that failure
is the point: a card with audio and no transcript is a card a facilitator can still answer.
"""

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ProjectRole
from app.core.exceptions import UpstreamServiceError
from app.db.models.internalization_room import IRQuestion, IRQuestionStatus
from app.services.internalization_room import questions as service
from app.services.internalization_room.canon.elements import element_keys
from app.services.platform import audio_duration
from tests.baker import (
    grant_facilitator_app_role,
    make_language,
    make_project,
    make_project_user_access,
    make_user,
)

#: A real recording rather than bytes assembled here. A container written by this test would
#: be measured by the reader this test is checking, and the two would agree with each other
#: while both drift from what a tablet actually writes. Generated with ffmpeg, 1.5 s, and
#: deliberately without `+faststart`: a phone leaves `moov` at the end of the file, which is
#: the layout the measurement has to survive.
FIXTURE = Path(__file__).parent / "fixtures" / "pergunta-1500ms.m4a"
RECORDED_MS = 1500

#: What "matches the audio" means here. The container declares its own duration and the AAC
#: frames it holds are 1024 samples each, so the declared length and the sum of the frames
#: are allowed to disagree by a frame or two — about 23 ms at 44.1 kHz. 50 ms leaves room for
#: that without leaving room for a wrong answer: half a second off would pass no reading of
#: this number.
TOLERANCE_MS = 50

DEVICE = "tablet-da-equipe-1"
PERICOPE = "P03"
#: A key out of the Meaning Map's own canon rather than one invented here. The column is
#: opaque to the server — nothing validates it, by design, since the app is the side that
#: knows which bead the hand went up on — so a made-up string would pass every assertion
#: below while proving nothing about the shape the app actually sends.
ELEMENT = element_keys(PERICOPE)[0]
SAID = "por que ela volta para Belem se nao tem ninguem la"


class MemoryStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def get(self, key: str) -> bytes | None:
        return self.objects.get(key)

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = data


def recorded() -> bytes:
    return FIXTURE.read_bytes()


def a_transcriber(text: str):
    async def stt(audio: bytes, *, language: str, mime_type: str) -> str:
        return text

    return stt


async def _raise(db: AsyncSession, store: MemoryStore, **kw):
    given = {
        "device_id": DEVICE,
        "session_id": "sessao-1",
        "pericope": PERICOPE,
        "audio": recorded(),
        "store": store,
        "stt": a_transcriber(SAID),
    }
    given.update(kw)
    return await service.raise_question(db, **given)


async def a_team_and_its_facilitator(db: AsyncSession):
    language = await make_language(db, name="Terena", code="tqe")
    team = await make_project(db, language.id, name="Equipe Terena")
    facilitator = await make_user(db, email="facilitadora@example.com")
    await make_project_user_access(db, team.id, facilitator.id, role=ProjectRole.FACILITATOR)
    await grant_facilitator_app_role(db, facilitator.id)
    return team, facilitator


async def auth_header(db: AsyncSession, user) -> dict[str, str]:
    from app.services.auth.issue_tokens import issue_tokens

    access, _refresh = await issue_tokens(db, user)
    return {"Authorization": f"Bearer {access}"}


INBOX = "/api/internalization-room/facilitator/questions"


@pytest.fixture()
async def desk_client(db_session: AsyncSession):
    """The facilitator's side of the question router, signed in as a person."""
    import httpx
    from fastapi import FastAPI
    from httpx import ASGITransport

    from app.api.internalization_room.questions import router as questions_router
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    test_app = FastAPI()
    test_app.include_router(questions_router, prefix="/api/internalization-room")
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    async with httpx.AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as client:
        yield client


async def test_how_long_the_recording_runs_is_read_from_the_audio(
    db_session: AsyncSession,
) -> None:
    question = await _raise(db_session, MemoryStore())

    assert question.duration_ms is not None
    assert abs(question.duration_ms - RECORDED_MS) <= TOLERANCE_MS


def test_the_room_has_no_way_to_say_how_long_its_recording_was() -> None:
    """There is no parameter to say it with, and that absence is what "not trusted" means.

    A field the client fills is a field the client gets wrong: a recorder that stops early,
    an app that sends the wall clock instead of the take, and the inbox then sorts and draws
    a number nothing produced. Read off the mounted route rather than the service signature,
    because the client's reach is the route.
    """
    from app.main import app

    (raise_hand,) = [
        route
        for route in app.routes
        if getattr(route, "path", "") == "/api/internalization-room/questions"
        and "POST" in getattr(route, "methods", set())
    ]
    accepted = {
        field.name
        for field in raise_hand.dependant.body_params
        + raise_hand.dependant.query_params
        + raise_hand.dependant.header_params
    }

    assert not [name for name in accepted if "duration" in name], accepted


async def test_the_element_the_hand_went_up_on_is_kept(db_session: AsyncSession) -> None:
    question = await _raise(db_session, MemoryStore(), element_key=ELEMENT)

    assert question.element_key == ELEMENT


async def test_a_question_that_names_no_element_is_still_a_question(
    db_session: AsyncSession,
) -> None:
    """Older rows and apps that have not shipped ENG-456 name no element. They still count."""
    question = await _raise(db_session, MemoryStore())

    assert question.element_key is None
    assert question.status is IRQuestionStatus.OPEN


async def test_what_was_said_is_transcribed_and_kept(db_session: AsyncSession) -> None:
    question = await _raise(db_session, MemoryStore())

    assert question.transcript == SAID


async def test_a_transcription_that_fails_does_not_lose_the_question(
    db_session: AsyncSession,
) -> None:
    """The card appears with audio and no transcript, and the hand is still answerable.

    The failure raised is the one the platform's STT raises on an outage, rather than an
    exception invented here: a test that proves the ingest survives `RuntimeError` proves
    nothing about the day ElevenLabs answers 503.
    """
    store = MemoryStore()

    async def refuses(audio: bytes, *, language: str, mime_type: str) -> str:
        raise UpstreamServiceError("Transcription request failed with status 503")

    question = await _raise(db_session, store, stt=refuses)

    assert question.transcript is None
    assert store.objects[question.audio_key] == recorded()
    assert await service.get_question(db_session, question.id) is not None


async def test_a_transcriber_that_is_broken_is_not_mistaken_for_a_provider_that_is_down(
    db_session: AsyncSession,
) -> None:
    """The three ways a provider fails are tolerated; a defect of ours is not swallowed.

    Widening the ingest's `except` to every exception costs nothing that any other case in
    this file can see, which is exactly why this one is here: a `TypeError` on this path is
    a mistake in this repository, and a mistake that silently produces questions with no
    transcript is one nobody finds. The question is committed before the transcription is
    attempted, so it survives either way — what differs is whether the defect is visible.
    """
    store = MemoryStore()

    async def broken(audio: bytes, *, language: str, mime_type: str) -> str:
        raise TypeError("o transcritor foi chamado errado")

    with pytest.raises(TypeError):
        await _raise(db_session, store, stt=broken)

    (kept,) = (await db_session.execute(select(IRQuestion))).scalars().all()
    assert kept.transcript is None
    assert store.objects[kept.audio_key] == recorded()


async def test_a_duration_that_cannot_be_measured_does_not_lose_the_question(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ffprobe missing is a broken machine, not a bad question."""
    monkeypatch.setenv("PATH", "")

    question = await _raise(db_session, MemoryStore())

    assert question.duration_ms is None
    assert await service.get_question(db_session, question.id) is not None


async def test_bytes_that_are_not_audio_have_no_duration() -> None:
    assert await audio_duration.measure_ms(b"isto nao e audio nenhum") is None


async def test_the_inbox_serves_all_three_on_the_card(
    db_session: AsyncSession, desk_client
) -> None:
    """Read off the route rather than off the service, because the Desk reads the route.

    A page object carrying the columns says nothing about what crosses the wire: the response
    model is a separate declaration, and a field left out of it is invisible to exactly the
    reader this issue is about.
    """
    team, facilitator = await a_team_and_its_facilitator(db_session)
    await _raise(db_session, MemoryStore(), project_id=team.id, element_key=ELEMENT)

    answer = await desk_client.get(INBOX, headers=await auth_header(db_session, facilitator))

    assert answer.status_code == 200, answer.text
    (card,) = answer.json()["questions"]
    assert card["element_key"] == ELEMENT
    assert card["transcript"] == SAID
    assert abs(card["duration_ms"] - RECORDED_MS) <= TOLERANCE_MS


async def test_a_card_with_nothing_but_audio_still_reaches_the_desk(
    db_session: AsyncSession, desk_client
) -> None:
    """The three absences at once: no element, no transcript, no duration.

    This is what an older row looks like, and what a question raised on the day both the
    transcriber and ffprobe are unavailable looks like. The Desk has to be handed a card it
    can draw, with the audio it can play, rather than a page that omits the question.
    """
    team, facilitator = await a_team_and_its_facilitator(db_session)
    question = await _raise(db_session, MemoryStore(), project_id=team.id)
    question.element_key = None
    question.transcript = None
    question.duration_ms = None
    await db_session.commit()

    answer = await desk_client.get(INBOX, headers=await auth_header(db_session, facilitator))

    (card,) = answer.json()["questions"]
    assert card["element_key"] is None
    assert card["transcript"] is None
    assert card["duration_ms"] is None
    assert card["audio_url"].endswith(f"/questions/{question.id}/audio")
