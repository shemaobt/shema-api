"""What a turn leaves behind when the room never gets to speak it.

Read from the endpoint and then from a second database session, because the fact under
test is durability: a probe and a ledger event committed by a turn that failed before the
team heard anything are still there on the next request, and the next answer is then
assessed against a question nobody asked. Re-reading through the request's own session
would only show its identity map, which is not what survives.
"""

import json
import sys
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models.internalization_room import IRSession, IRSessionStatus
from app.services.internalization_room.comprehension.checkpoints import checkpoints_for
from app.services.internalization_room.comprehension.evidence import EvidenceMethod
from app.services.internalization_room.comprehension.probe import ActiveProbe, ProbePurpose
from app.services.internalization_room.sessions import (
    append_exchange,
    comprehension_of,
    create_session,
    save_comprehension,
)
from app.services.platform.tts import SynthesizedSpeech

PREFIX = "/api/internalization-room"
KEY = "sala-de-teste"
P = "P03"
FIRST_QUESTION = "Quem aparece nesta parte?"
GUIDE_LINE = "Vamos ficar nesta cena. O que vocês contariam?"
TEAM_ANSWER = "Noemi voltou para Belém com Rute no tempo da colheita"
EXCERPT = "Noemi voltou"


class _SynthesisThatCanBreak:
    """The room's voice, breaking on demand.

    Breaking it is how this file reaches the moment under test — the turn is decided and
    the state is ready, and the team has still heard nothing.
    """

    def __init__(self) -> None:
        self.working = True
        self.spoken: list[str] = []

    async def __call__(self, text: str, **_: Any) -> tuple[SynthesizedSpeech, bool]:
        if not self.working:
            raise RuntimeError("the voice service is down")
        self.spoken.append(text)
        entry = SynthesizedSpeech(
            audio=b"audio",
            mime_type="audio/mpeg",
            etag="e",
            cached=False,
            key=f"tts/voice/m/f/{abs(hash(text))}.mp3",
        )
        return entry, False


@pytest.fixture()
async def voice() -> _SynthesisThatCanBreak:
    return _SynthesisThatCanBreak()


@pytest.fixture()
async def reread(test_engine):
    """The session as the next request would load it: a new connection, no identity map."""

    async def _reread(session_id: str) -> IRSession:
        factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
        async with factory() as fresh:
            loaded = await fresh.get(IRSession, session_id)
            assert loaded is not None
            return loaded

    return _reread


@pytest.fixture()
async def client(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, voice: _SynthesisThatCanBreak
):
    """The endpoint as the tablet reaches it, answering with whatever the handlers produce.

    ``raise_app_exceptions=False`` because one of these tests is about the status the app
    still receives: re-raising would leave no response to assert on.
    """
    from fastapi import FastAPI

    from app.api.internalization_room import router
    from app.api.internalization_room import sessions as sessions_api
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    monkeypatch.setattr(get_settings(), "internalization_room_api_key", KEY, raising=False)
    monkeypatch.setattr(sessions_api.room, "synthesize_facilitator_speech", voice)

    async def _heard(audio: bytes, **_: Any) -> Any:
        from app.services.internalization_room.hearing import HeardSpeech

        return HeardSpeech(text=TEAM_ANSWER)

    monkeypatch.setattr(sessions_api, "heard_speech", _heard)

    test_app = FastAPI()
    test_app.include_router(router, prefix=PREFIX)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class _AgreeingModels:
    """A Guide that drafts one short line and a Validator that passes it."""

    async def __call__(self, *, system_prompt: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return GUIDE_LINE


@pytest.fixture()
def models_agree(monkeypatch: pytest.MonkeyPatch, target_checkpoint: str) -> None:
    monkeypatch.setattr(
        sys.modules["app.services.internalization_room.run_turn"], "call_agent", _AgreeingModels()
    )

    async def _assessor(**_: Any) -> str:
        return json.dumps(
            {
                "observations": [
                    {
                        "checkpoint_id": target_checkpoint,
                        "result": "demonstrated",
                        "evidence_excerpt": EXCERPT,
                        "rationale": "names the return",
                    }
                ],
                "mother_tongue_practice_reported": False,
                "practice_evidence_excerpt": "",
            }
        )

    monkeypatch.setattr(
        sys.modules["app.services.internalization_room.comprehension.assessor"],
        "call_agent",
        _assessor,
    )


@pytest.fixture()
def target_checkpoint() -> str:
    return next(checkpoint for checkpoint in checkpoints_for(P) if checkpoint.critical).id


@pytest.fixture()
async def waiting_room(db_session: AsyncSession, target_checkpoint: str) -> IRSession:
    """A room that has asked its question and is waiting on the answer."""
    session = await create_session(
        db_session, language="pt", pericope=P, bridge_mode="guided_microchecks"
    )
    session = await append_exchange(
        db_session, session, team_utterance="", guide_response=FIRST_QUESTION
    )
    state = comprehension_of(session)
    state.active_probe = ActiveProbe(
        id="probe-1",
        checkpoint_ids=[target_checkpoint],
        method=EvidenceMethod.MICRO_TELLBACK,
        purpose=ProbePurpose.INITIAL_CHECK,
    )
    return await save_comprehension(db_session, session, state)


async def _the_team_answers(client: httpx.AsyncClient, session_id: str) -> httpx.Response:
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/turns",
        headers={"X-Room-Key": KEY},
        files={"file": ("answer.m4a", b"audio", "audio/m4a")},
    )


def _guide_lines(session: IRSession) -> list[str]:
    return [
        message.get("text", "")
        for message in (session.messages or [])
        if message.get("role") == "guide"
    ]


async def test_a_turn_the_room_never_spoke_leaves_no_probe_waiting_on_it(
    client: httpx.AsyncClient,
    waiting_room: IRSession,
    voice: _SynthesisThatCanBreak,
    models_agree: None,
    reread,
) -> None:
    """A question nobody heard cannot be the one the next answer is judged against.

    The probe is the room's authorization to assess what comes next. Committing a new one
    for a turn that died before the voice went out points that authorization at a question
    the team was never asked.
    """
    voice.working = False

    await _the_team_answers(client, waiting_room.id)

    after = comprehension_of(await reread(waiting_room.id))
    assert after.active_probe is not None
    assert after.active_probe.id == "probe-1"


async def test_a_turn_the_room_never_spoke_records_no_evidence_for_it(
    client: httpx.AsyncClient,
    waiting_room: IRSession,
    voice: _SynthesisThatCanBreak,
    models_agree: None,
    reread,
) -> None:
    """What the session knows it asked and what it holds as evidence describe one turn.

    This is the damage: the ledger gains an observation while the exchange that would have
    recorded the question is never appended, so the room's evidence outruns its own
    conversation by a turn and nothing afterwards can tell.
    """
    voice.working = False

    await _the_team_answers(client, waiting_room.id)

    session = await reread(waiting_room.id)
    assert comprehension_of(session).ledger == []
    assert _guide_lines(session) == [FIRST_QUESTION]


async def test_a_turn_the_room_did_speak_is_remembered_whole(
    client: httpx.AsyncClient,
    waiting_room: IRSession,
    voice: _SynthesisThatCanBreak,
    models_agree: None,
    reread,
) -> None:
    """The counterweight. A room that speaks and forgets is worse than one that remembers
    too eagerly, so the happy path has to keep every one of the three writes."""
    answered = await _the_team_answers(client, waiting_room.id)

    assert answered.status_code == 200, answered.text[:300]
    session = await reread(waiting_room.id)
    state = comprehension_of(session)
    assert state.ledger, "a evidência do turno falado tem de ficar gravada"
    assert _guide_lines(session) == [FIRST_QUESTION, GUIDE_LINE]
    assert voice.spoken == [GUIDE_LINE]


async def test_a_room_that_cannot_speak_still_says_so_to_the_tablet(
    client: httpx.AsyncClient,
    waiting_room: IRSession,
    voice: _SynthesisThatCanBreak,
    models_agree: None,
) -> None:
    """The fix is about what is kept, not about hiding the failure.

    A silent 200 would leave the app with no line to play and no reason why, which is the
    one outcome worse than the error it already shows.
    """
    voice.working = False

    answered = await _the_team_answers(client, waiting_room.id)

    assert answered.status_code == 500


async def test_a_turn_that_fails_after_the_voice_still_reaches_no_one(
    client: httpx.AsyncClient,
    waiting_room: IRSession,
    voice: _SynthesisThatCanBreak,
    models_agree: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Speaking first does not create a turn the team heard but the room forgot.

    A synthesized clip reaches the team only as the handle in this response, so a request
    that fails after synthesis hands the app nothing to play. The clip is left paid for in
    the bucket, where the retry finds it.
    """
    from app.api.internalization_room import sessions as sessions_api

    async def _the_database_goes_away(*_args: Any, **_kwargs: Any) -> IRSession:
        raise RuntimeError("the database went away")

    monkeypatch.setattr(sessions_api.room, "append_exchange", _the_database_goes_away)

    answered = await _the_team_answers(client, waiting_room.id)

    assert answered.status_code == 500
    assert "audio_url" not in answered.text


@pytest.fixture()
def the_assessor_is_down(monkeypatch: pytest.MonkeyPatch) -> None:
    """The Guide and Validator work; only the comprehension assessor cannot be reached."""
    monkeypatch.setattr(
        sys.modules["app.services.internalization_room.run_turn"], "call_agent", _AgreeingModels()
    )

    async def _assessor(**_: Any) -> str:
        raise RuntimeError("assessor transport is down")

    monkeypatch.setattr(
        sys.modules["app.services.internalization_room.comprehension.assessor"],
        "call_agent",
        _assessor,
    )


async def test_the_hard_stop_outlives_the_request_that_raised_it(
    client: httpx.AsyncClient,
    waiting_room: IRSession,
    the_assessor_is_down: None,
    reread,
) -> None:
    """Asking for a person has to survive the turn that asked.

    `append_exchange` releases `NEEDS_PERSON` on every landed turn, and it runs in this same
    request — so a halt taken inside `run_comprehension_turn` would be undone one line later
    and the room would go on asking. Read from a second connection, because the fact under
    test is what the next request loads.
    """
    for _ in range(4):
        response = await _the_team_answers(client, waiting_room.id)
        assert response.status_code == 200
    assert (await reread(waiting_room.id)).status is IRSessionStatus.IN_PROGRESS

    response = await _the_team_answers(client, waiting_room.id)

    assert response.status_code == 200
    assert response.json()["used_fail_safe"]
    assert (await reread(waiting_room.id)).status is IRSessionStatus.NEEDS_PERSON


async def test_the_pause_is_not_a_latch(
    client: httpx.AsyncClient,
    waiting_room: IRSession,
    the_assessor_is_down: None,
    reread,
) -> None:
    """A person comes back, the team speaks, and the room leaves the pause on its own.

    The hard stop clears the probe and spends the count, so the turn after it never reaches
    the assessor — it lands, and a turn that lands is the proof a person came back.
    """
    for _ in range(5):
        await _the_team_answers(client, waiting_room.id)
    assert (await reread(waiting_room.id)).status is IRSessionStatus.NEEDS_PERSON

    await _the_team_answers(client, waiting_room.id)

    assert (await reread(waiting_room.id)).status is IRSessionStatus.IN_PROGRESS
