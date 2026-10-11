"""The passage's first line, written while the team is still hearing the panorama.

Every other turn waits on what the team just said. The opening does not — the team has not
spoken, the coverage is untouched, the conversation is empty — so it is the one line that can
be written before it is asked for. Doing that turns a five-second wait into none.
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.internalization_room import IRSession, IRSessionStatus
from app.services.internalization_room.prepare_opening import hand_over, take_prepared
from tests.device_harness import TABLET_TEAM, a_linked_tablet


async def _session(db: AsyncSession, **over: object) -> IRSession:
    fields: dict[str, object] = {
        "pericope": "P01",
        "status": IRSessionStatus.IN_PROGRESS,
        "messages": [],
        "coverage_state": {},
        "kept_takes": {},
        "back_translation": {},
        "language": "pt",
    }
    fields.update(over)
    session = IRSession(**fields)
    db.add(session)
    await db.commit()
    return session


async def _stored_prepared(db: AsyncSession, session: IRSession) -> str | None:
    return await db.scalar(
        select(IRSession.prepared_speech)
        .where(IRSession.id == session.id)
        .execution_options(populate_existing=True)
    )


async def test_a_ready_line_is_handed_to_the_session_that_speaks_it(
    db_session: AsyncSession,
) -> None:
    panorama = await _session(
        db_session,
        pericope="OV-Ruth",
        prepared_speech="Olá.",
        prepared_audio_key="tts/x.mp3",
        prepared_pericope="P01",
    )
    passage = await _session(db_session)

    assert await hand_over(db_session, panorama, passage) is True
    assert await _stored_prepared(db_session, passage) == "Olá."
    assert await _stored_prepared(db_session, panorama) is None


async def test_another_passage_is_not_given_the_first_passage_line(
    db_session: AsyncSession,
) -> None:
    """The panorama writes ahead for P01 only; P03 would hear P01's framing as its own."""
    panorama = await _session(
        db_session,
        pericope="OV-Ruth",
        prepared_speech="Olá.",
        prepared_audio_key="tts/x.mp3",
        prepared_pericope="P01",
    )
    other = await _session(db_session, pericope="P03")

    assert await hand_over(db_session, panorama, other) is False
    assert await _stored_prepared(db_session, other) is None
    assert await _stored_prepared(db_session, panorama) == "Olá."


async def test_a_panorama_still_writing_hands_over_nothing(db_session: AsyncSession) -> None:
    """The team may enter before it is ready; then the session simply writes its own."""
    panorama = await _session(db_session, pericope="OV-Ruth")

    assert await hand_over(db_session, panorama, await _session(db_session)) is False


async def test_half_a_line_is_not_a_line(db_session: AsyncSession) -> None:
    only_text = await _session(
        db_session, pericope="OV-Ruth", prepared_speech="Olá.", prepared_pericope="P01"
    )
    assert await hand_over(db_session, only_text, await _session(db_session)) is False

    only_audio = await _session(
        db_session, pericope="OV-Ruth", prepared_audio_key="tts/x.mp3", prepared_pericope="P01"
    )
    assert await hand_over(db_session, only_audio, await _session(db_session)) is False


async def test_the_prepared_line_is_spoken_once_and_then_gone(db_session: AsyncSession) -> None:
    """A second turn must never repeat the opening — it is consumed when taken."""
    session = await _session(db_session, prepared_speech="Olá.", prepared_audio_key="tts/x.mp3")

    assert await take_prepared(db_session, session) == ("Olá.", "tts/x.mp3", [])
    assert await take_prepared(db_session, session) is None


async def test_a_session_with_nothing_prepared_says_so(db_session: AsyncSession) -> None:
    session = await _session(db_session)

    assert await take_prepared(db_session, session) is None


async def test_a_prepared_line_is_handed_over_once(db_session: AsyncSession) -> None:
    panorama = await _session(
        db_session,
        pericope="OV-Ruth",
        prepared_speech="a primeira fala",
        prepared_audio_key="tts/v/p01.mp3",
        prepared_pericope="P01",
    )
    first = await _session(db_session)
    second = await _session(db_session)

    assert await hand_over(db_session, panorama, first) is True
    assert await hand_over(db_session, panorama, second) is False, (
        "a origem nunca era limpa, então a mesma fala ia para toda sessão seguinte"
    )


PREPARED = "Vamos ficar no começo: uma família sai de Belém por falta de comida."
PANORAMA = "Bem-vindos. Este livro inteiro é uma volta para casa, em quatro movimentos."
ON_DEMAND = "Uma linha escrita na hora, porque nada estava pronto."
IR = "/api/internalization-room"


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

    async def _panorama_turn(**_: Any) -> TurnOutcome:
        return TurnOutcome(speech=PANORAMA, transcript="")

    async def _comprehension_turn(*_: Any, **__: Any) -> ComprehensionTurn:
        return ComprehensionTurn(
            outcome=TurnOutcome(speech=ON_DEMAND, transcript=""),
            state=ComprehensionState(),
        )

    async def _speech(text: str, **_: Any) -> tuple[SynthesizedSpeech, bool]:
        return SynthesizedSpeech(
            audio=b"audio",
            mime_type="audio/mpeg",
            etag="e",
            cached=False,
            key=f"tts/{get_settings().internalization_room_voice_id}/m/f/{abs(hash(text))}.mp3",
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
    tablet = await a_linked_tablet(db_session, team_id=TABLET_TEAM)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", headers=tablet.headers
    ) as c:
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
    panorama.prepared_audio_key = (
        f"tts/{get_settings().internalization_room_voice_id}/m/f/prepared.mp3"
    )
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
    created = await client.post(f"{IR}/sessions", json={"pericope": "OV"})
    assert created.status_code == 200, created.text[:200]
    return created.json()["session_id"]


async def _open_it(client, session_id: str):
    opened = await client.post(f"{IR}/sessions/{session_id}/turns")
    assert opened.status_code == 200, opened.text[:200]
    return opened


async def _passage_after(client, panorama_id: str, pericope: str = "P01") -> str:
    created = await client.post(
        f"{IR}/sessions",
        json={"pericope": pericope, "after_session": panorama_id},
    )
    assert created.status_code == 200, created.text[:200]
    return created.json()["session_id"]


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


async def test_a_panorama_opened_before_the_preparation_lands_still_opens(
    client, db_session: AsyncSession
) -> None:
    """The ordinary case, where the race does not happen at all."""
    panorama = await _create_panorama(client)

    await _open_it(client, panorama)
    said = await _the_room_said(db_session, panorama)

    assert PANORAMA in said
    assert PREPARED not in said


async def test_the_ready_line_reaches_the_team_without_ever_reaching_the_classifier(
    client, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The opening is a turn like any other now, whichever door wrote it.

    The prepared path used to hand every ready line to the classifier unconditionally,
    before the settle gate the on-demand door reads could ever see it — a second door
    the rule could not reach through. Coverage is `engaged`-only on the team's screen, so
    a line the room wrote for itself is not evidence of anything the team heard, whether it
    was written on demand or ahead of time.
    """
    from app.api.internalization_room import sessions as sessions_api

    settled: list[dict[str, str]] = []

    async def _record(**handed: str) -> None:
        settled.append(handed)

    monkeypatch.setattr(sessions_api, "settle_coverage", _record)

    panorama = await _create_panorama(client)
    await _park_the_prepared_line(db_session, panorama)
    passage = await _passage_after(client, panorama)
    await _open_it(client, passage)

    assert await _the_room_said(db_session, passage) == PREPARED
    assert settled == [], (
        "a abertura preparada chegava ao classificador por uma porta que o portão da "
        "abertura ao vivo não lê, e coverage é engaged-only na tela do time"
    )


OLD = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)


async def _long_ago(db_session: AsyncSession, *session_ids: str) -> None:
    for session_id in session_ids:
        await db_session.execute(
            update(IRSession)
            .where(IRSession.id == session_id)
            .values(updated_at=OLD)
            .execution_options(synchronize_session=False)
        )
    await db_session.commit()


async def _updated_at(db_session: AsyncSession, session_id: str) -> datetime:
    stored = await db_session.scalar(
        select(IRSession.updated_at)
        .where(IRSession.id == session_id)
        .execution_options(populate_existing=True)
    )
    assert stored is not None
    return stored.replace(tzinfo=UTC)


async def test_a_panoramas_updated_at_stays_as_it_was_when_its_background_preparation_lands(
    client, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    from app.services.internalization_room import prepare_opening as module
    from app.services.internalization_room.run_turn import TurnOutcome

    async def _written(**_: object) -> TurnOutcome:
        return TurnOutcome(speech=PREPARED, transcript="")

    async def _voiced(*_: object, **__: object) -> tuple[SimpleNamespace, None]:
        return SimpleNamespace(key="tts/prepared.mp3"), None

    async def _the_passage(*_: object, **__: object) -> str:
        return "P01"

    monkeypatch.setattr(module, "run_turn", _written)
    monkeypatch.setattr(module, "synthesize_facilitator_speech", _voiced)
    monkeypatch.setattr(module, "active_passage", _the_passage)
    panorama = await _create_panorama(client)
    await _long_ago(db_session, panorama)

    await module.prepare_opening(panorama)

    assert await _prepared_speech_of(db_session, panorama) == PREPARED
    assert await _updated_at(db_session, panorama) == OLD


async def _prepared_speech_of(db_session: AsyncSession, session_id: str) -> str | None:
    return await db_session.scalar(
        select(IRSession.prepared_speech)
        .where(IRSession.id == session_id)
        .execution_options(populate_existing=True)
    )


async def test_a_panoramas_updated_at_stays_as_it_was_when_the_team_opens_a_passage_and_the_prepared_opening_is_handed_over(  # noqa: E501
    client, db_session: AsyncSession
) -> None:
    panorama = await _create_panorama(client)
    await _park_the_prepared_line(db_session, panorama)
    await _long_ago(db_session, panorama)

    passage = await _passage_after(client, panorama)

    assert await _prepared_speech_of(db_session, passage) == PREPARED
    assert await _prepared_speech_of(db_session, panorama) is None
    assert await _updated_at(db_session, panorama) == OLD


async def test_the_opening_sessions_updated_at_is_not_moved_by_the_hand_over(
    client, db_session: AsyncSession
) -> None:
    panorama = await _create_panorama(client)
    passage = await _passage_after(client, panorama)
    await _park_the_prepared_line(db_session, panorama)
    await _long_ago(db_session, panorama, passage)

    resumed = await _passage_after(client, panorama)

    assert resumed == passage
    assert await _prepared_speech_of(db_session, passage) == PREPARED
    assert await _updated_at(db_session, passage) == OLD


async def test_a_team_turn_moves_the_sessions_updated_at(client, db_session: AsyncSession) -> None:
    from app.services.internalization_room import sessions as room

    panorama = await _create_panorama(client)
    await _long_ago(db_session, panorama)
    session = await room.get_session(db_session, panorama)

    await room.append_exchange(db_session, session, team_utterance="oi", guide_response="ok")

    assert await _updated_at(db_session, panorama) > OLD
