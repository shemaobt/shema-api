"""The passage's first line, written while the team is still hearing the panorama.

Every other turn waits on what the team just said. The opening does not — the team has not
spoken, the coverage is untouched, the conversation is empty — so it is the one line that can
be written before it is asked for. Doing that turns a five-second wait into none.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession, IRSessionStatus
from app.services.internalization_room.prepare_opening import hand_over, take_prepared


def _session(**over: object) -> IRSession:
    fields: dict[str, object] = {
        "id": "s1",
        "pericope": "P01",
        "status": IRSessionStatus.IN_PROGRESS,
        "messages": [],
        "coverage_state": {},
        "kept_takes": {},
        "back_translation": {},
    }
    fields.update(over)
    return IRSession(**fields)


def test_a_ready_line_is_handed_to_the_session_that_speaks_it() -> None:
    panorama = _session(
        id="ov",
        prepared_speech="Olá.",
        prepared_audio_key="tts/x.mp3",
        prepared_pericope="P01",
    )
    passage = _session(id="p")

    assert hand_over(panorama, passage) is True
    assert passage.prepared_speech == "Olá."
    assert passage.prepared_audio_key == "tts/x.mp3"


def test_another_passage_is_not_given_the_first_passage_line() -> None:
    """The panorama writes ahead for P01 only; P03 would hear P01's framing as its own."""
    panorama = _session(id="ov", prepared_speech="Olá.", prepared_audio_key="tts/x.mp3")
    other = _session(id="p", pericope="P03")

    assert hand_over(panorama, other) is False
    assert other.prepared_speech is None
    assert panorama.prepared_speech == "Olá."


def test_a_panorama_still_writing_hands_over_nothing() -> None:
    """The team may enter before it is ready; then the session simply writes its own."""
    assert hand_over(_session(id="ov"), _session(id="p")) is False


def test_half_a_line_is_not_a_line() -> None:
    only_text = _session(id="ov", prepared_speech="Olá.")
    assert hand_over(only_text, _session(id="p")) is False

    only_audio = _session(id="ov", prepared_audio_key="tts/x.mp3")
    assert hand_over(only_audio, _session(id="p")) is False


@pytest.mark.asyncio
async def test_the_prepared_line_is_spoken_once_and_then_gone(db_session: AsyncSession) -> None:
    """A second turn must never repeat the opening — it is consumed when taken."""
    session = _session(prepared_speech="Olá.", prepared_audio_key="tts/x.mp3")
    db_session.add(session)
    await db_session.commit()

    assert await take_prepared(db_session, session) == ("Olá.", "tts/x.mp3")
    assert await take_prepared(db_session, session) is None


@pytest.mark.asyncio
async def test_a_session_with_nothing_prepared_says_so(db_session: AsyncSession) -> None:
    session = _session()
    db_session.add(session)
    await db_session.commit()

    assert await take_prepared(db_session, session) is None


def test_the_prepared_line_belongs_to_the_passage_it_was_written_for() -> None:
    """It is written from one passage's meaning map, and delivered as that passage's words.

    A team choosing P03 heard P01's opening as P03's framing, to people who cannot read
    and have no way to check.

    The comparison is against the passage recorded when the line was written, not against the
    constant this used to hold nor against a fresh resolution — see ENG-450's own case for why
    the third of those is not the same guard.
    """
    panorama = IRSession(id="ov", pericope="OV-Ruth", prepared_pericope="P01")
    panorama.prepared_speech = "a primeira fala da P01"
    panorama.prepared_audio_key = "tts/v/p01.mp3"

    outra = IRSession(id="s2", pericope="P03")

    assert hand_over(panorama, outra) is False
    assert outra.prepared_speech is None


def test_a_prepared_line_is_handed_over_once() -> None:
    panorama = IRSession(id="ov", pericope="OV-Ruth", prepared_pericope="P01")
    panorama.prepared_speech = "a primeira fala"
    panorama.prepared_audio_key = "tts/v/p01.mp3"

    first = IRSession(id="s1", pericope="P01")
    second = IRSession(id="s2", pericope="P01")

    assert hand_over(panorama, first) is True
    assert hand_over(panorama, second) is False, (
        "a origem nunca era limpa, então a mesma fala ia para toda sessão seguinte"
    )


PREPARED = "Vamos ficar no começo: uma família sai de Belém por falta de comida."
PANORAMA = "Bem-vindos. Este livro inteiro é uma volta para casa, em quatro movimentos."
ON_DEMAND = "Uma linha escrita na hora, porque nada estava pronto."
IR = "/api/internalization-room"
ROOM_KEY = "sala-de-teste"


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    """The room over HTTP, with every model and every background task stood in for.

    Nothing here is asserted on: the doubles exist so each path speaks a line this file can
    tell apart, which is what makes "which opening did the team hear" an observable question.
    """
    from typing import Any

    import httpx
    from fastapi import FastAPI
    from httpx import ASGITransport

    from app.api.internalization_room import router as room_router
    from app.api.internalization_room import sessions as sessions_api
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers
    from app.services.internalization_room.comprehension.state import ComprehensionState
    from app.services.internalization_room.live_turn import ComprehensionTurn
    from app.services.internalization_room.run_turn import TurnOutcome
    from app.services.platform.tts import SynthesizedSpeech

    monkeypatch.setattr(get_settings(), "internalization_room_api_key", ROOM_KEY, raising=False)

    async def _panorama_turn(**_: Any) -> TurnOutcome:
        return TurnOutcome(speech=PANORAMA, transcript="")

    async def _comprehension_turn(*_: Any, **__: Any) -> ComprehensionTurn:
        return ComprehensionTurn(
            outcome=TurnOutcome(speech=ON_DEMAND, transcript=""),
            bridge_mode="adaptive",
            state=ComprehensionState(),
        )

    async def _speech(text: str, **_: Any) -> tuple[SynthesizedSpeech, bool]:
        return SynthesizedSpeech(
            audio=b"audio",
            mime_type="audio/mpeg",
            etag="e",
            cached=False,
            key=f"tts/voice/m/f/{abs(hash(text))}.mp3",
        ), False

    async def _nothing(*_: Any, **__: Any) -> None:
        return None

    monkeypatch.setattr(sessions_api.room, "run_panorama_turn", _panorama_turn)
    monkeypatch.setattr(sessions_api.room, "run_comprehension_turn", _comprehension_turn)
    monkeypatch.setattr(sessions_api.room, "synthesize_facilitator_speech", _speech)
    monkeypatch.setattr(sessions_api, "prepare_opening", _nothing)
    monkeypatch.setattr(sessions_api, "settle_coverage", _nothing)

    test_app = FastAPI()
    test_app.include_router(room_router, prefix=IR)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _park_the_prepared_line(db_session: AsyncSession, session_id: str) -> None:
    """What the background preparation leaves behind when it wins the race.

    All three fields, as `prepare_opening` writes them: `hand_over` refuses a line whose
    passage was never recorded, so staging only the speech and the key stages a state the
    producer cannot produce.
    """
    from app.services.internalization_room.sessions import get_session

    panorama = await get_session(db_session, session_id)
    panorama.prepared_speech = PREPARED
    panorama.prepared_audio_key = "tts/voice/m/f/prepared.mp3"
    panorama.prepared_pericope = "P01"
    await db_session.commit()


async def _the_room_said(db_session: AsyncSession, session_id: str) -> str:
    """The last thing the room actually said in that session.

    A panorama opening also carries the bridge-language calibration question, so which
    opening the team heard is asked of the line rather than of the whole utterance.
    """
    from app.services.internalization_room.sessions import get_session

    session = await get_session(db_session, session_id)
    guide = [m for m in (session.messages or []) if m.get("role") == "guide"]
    return guide[-1]["text"] if guide else ""


async def _create_panorama(client) -> str:
    created = await client.post(
        f"{IR}/sessions", headers={"X-Room-Key": ROOM_KEY}, json={"pericope": "OV"}
    )
    assert created.status_code == 200, created.text[:200]
    return created.json()["session_id"]


async def _open_it(client, session_id: str):
    opened = await client.post(
        f"{IR}/sessions/{session_id}/turns", headers={"X-Room-Key": ROOM_KEY}
    )
    assert opened.status_code == 200, opened.text[:200]
    return opened


async def _passage_after(client, panorama_id: str, pericope: str = "P01") -> str:
    created = await client.post(
        f"{IR}/sessions",
        headers={"X-Room-Key": ROOM_KEY},
        json={"pericope": pericope, "after_session": panorama_id},
    )
    assert created.status_code == 200, created.text[:200]
    return created.json()["session_id"]


@pytest.mark.asyncio
async def test_the_panorama_does_not_open_by_speaking_the_first_passage(
    client, db_session: AsyncSession
) -> None:
    """The race, staged as it happens: the preparation lands before the team opens the book.

    The panorama is the shape of the whole book with no retelling asked. Speaking P01's
    opening there tells a team that has not chosen a passage that the choice is made.
    """
    panorama = await _create_panorama(client)
    await _park_the_prepared_line(db_session, panorama)

    await _open_it(client, panorama)
    said = await _the_room_said(db_session, panorama)

    assert PANORAMA in said
    assert PREPARED not in said


@pytest.mark.asyncio
async def test_a_passage_opened_after_a_panorama_still_gets_the_ready_line(
    client, db_session: AsyncSession
) -> None:
    """The counterweight. The preparation exists to spare the passage the wait, and closing
    the defect by switching it off would be no fix at all."""
    panorama = await _create_panorama(client)
    await _park_the_prepared_line(db_session, panorama)

    passage = await _passage_after(client, panorama)
    await _open_it(client, passage)

    assert await _the_room_said(db_session, passage) == PREPARED


@pytest.mark.asyncio
async def test_the_panorama_leaves_the_ready_line_for_the_passage_to_come(
    client, db_session: AsyncSession
) -> None:
    """The second harm: not speaking it is not enough, it must still be there afterwards.

    A guard that consumed the line and threw it away would pass the first test and still
    cost the team the wait the preparation was written to spare them.
    """
    panorama = await _create_panorama(client)
    await _park_the_prepared_line(db_session, panorama)
    await _open_it(client, panorama)

    passage = await _passage_after(client, panorama)
    await _open_it(client, passage)

    assert await _the_room_said(db_session, passage) == PREPARED


@pytest.mark.asyncio
async def test_a_panorama_opened_before_the_preparation_lands_still_opens(
    client, db_session: AsyncSession
) -> None:
    """The ordinary case, where the race does not happen at all."""
    panorama = await _create_panorama(client)

    await _open_it(client, panorama)
    said = await _the_room_said(db_session, panorama)

    assert PANORAMA in said
    assert PREPARED not in said
