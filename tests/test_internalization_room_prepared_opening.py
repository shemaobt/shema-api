"""The passage's first line, written while the team is still hearing the panorama.

Every other turn waits on what the team just said. The opening does not — the team has not
spoken, the conversation is empty, and the coverage is whatever necklace this team already
carries into the passage — so it is the one line that can be written before it is asked for.
Doing that turns a five-second wait into none.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import router as room_router
from app.core.database import get_db
from app.core.exceptions import register_exception_handlers
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


async def test_the_prepared_line_is_spoken_once_and_then_gone(db_session: AsyncSession) -> None:
    """A second turn must never repeat the opening — it is consumed when taken."""
    session = _session(prepared_speech="Olá.", prepared_audio_key="tts/x.mp3")
    db_session.add(session)
    await db_session.commit()

    assert await take_prepared(db_session, session) == ("Olá.", "tts/x.mp3")
    assert await take_prepared(db_session, session) is None


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


@asynccontextmanager
async def _room_client(db_session: AsyncSession) -> AsyncIterator[httpx.AsyncClient]:
    """The room's FastAPI app, wired to `db_session` in place of a real database.

    Shared by the `client` fixture below and by any test that wants the room over HTTP with
    its own doubles, so the two never drift on what "the app under test" means.
    """
    test_app = FastAPI()
    test_app.include_router(room_router, prefix=IR)
    register_exception_handlers(test_app)

    async def _get_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    """The room over HTTP, with every model and every background task stood in for.

    Nothing here is asserted on: the doubles exist so each path speaks a line this file can
    tell apart, which is what makes "which opening did the team hear" an observable question.
    """
    from typing import Any

    from app.api.internalization_room import sessions as sessions_api
    from app.core.config import get_settings
    from app.services.internalization_room.run_turn import TurnOutcome
    from app.services.platform.tts import SynthesizedSpeech

    monkeypatch.setattr(get_settings(), "internalization_room_api_key", ROOM_KEY, raising=False)

    async def _panorama_turn(**_: Any) -> TurnOutcome:
        return TurnOutcome(speech=PANORAMA, transcript="")

    async def _comprehension_turn(*_: Any, **__: Any) -> TurnOutcome:
        return TurnOutcome(speech=ON_DEMAND, transcript="")

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

    async with _room_client(db_session) as c:
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


async def test_the_ready_line_is_classified_once_and_its_replay_still_promises_it(
    client, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The opening is a turn like any other, whichever door wrote it: her route classifies
    the kickoff with no condition (`route.ts:179,185-194`). The app arms its wait for the
    settled frame only on `classification_pending` (`session_notifier.dart:1212-1219`), so the
    reply says so, and so does the replay a resent `turn_id` gets — which is not a second
    turn and is not classified again."""
    from app.api.internalization_room import sessions as sessions_api

    settled: list[dict[str, str]] = []

    async def _record(**handed: str) -> None:
        settled.append(handed)

    monkeypatch.setattr(sessions_api, "settle_coverage", _record)

    panorama = await _create_panorama(client)
    await _park_the_prepared_line(db_session, panorama)
    passage = await _passage_after(client, panorama)
    opened = await client.post(
        f"{IR}/sessions/{passage}/turns",
        headers={"X-Room-Key": ROOM_KEY},
        data={"turn_id": "abertura"},
    )
    again = await client.post(
        f"{IR}/sessions/{passage}/turns",
        headers={"X-Room-Key": ROOM_KEY},
        data={"turn_id": "abertura"},
    )

    assert opened.status_code == again.status_code == 200, opened.text[:200]
    assert await _the_room_said(db_session, passage) == PREPARED
    assert [
        (handed["turn_id"], handed["team_utterance"], handed["guide_response"], handed["opening"])
        for handed in settled
    ] == [("abertura", "", PREPARED, True)], (
        "a abertura preparada nunca chegava ao classificador, e o que o Guia levantou nela "
        "não ficava registrado como levantado"
    )
    assert opened.json()["classification_pending"] is True, (
        "a resposta da abertura preparada não dizia que o classificador corria, e o app não "
        "armava a espera pelo quadro de cobertura"
    )
    assert again.json()["classification_pending"] is True, (
        "o replay do turn_id guardava a promessa antiga, e o tablet que reenviou não esperava"
    )


async def test_the_prepared_opening_renders_the_teams_inherited_necklace(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A returning team's prepared opening wrote its ledger from a literal `{}`, never from
    the necklace this same team already carries — so the Guide's first line always read
    "nothing yet — the session is just beginning", even for a team most of the way through.
    """
    from types import SimpleNamespace
    from typing import Any

    from app.api.internalization_room import _deps
    from app.services.internalization_room import prepare_opening as prepare_opening_module
    from app.services.internalization_room import sessions as room
    from app.services.internalization_room.canon.elements import element_keys
    from app.services.internalization_room.coverage import CoverageStatus
    from app.services.internalization_room.prompt_blocks import coverage_status_block
    from app.services.internalization_room.run_turn import TurnOutcome
    from app.services.platform.tts import SynthesizedSpeech
    from tests.baker import make_language, make_project

    pericope = "P01"
    language = await make_language(db_session, name="Ledger herdado", code="hld")
    team = await make_project(db_session, language.id, name="Ledger herdado")
    keys = element_keys(pericope)
    tuesday = await room.create_session(db_session, pericope=pericope, project_id=team.id)
    await room.apply_coverage(db_session, tuesday.id, {keys[0]: CoverageStatus.ENGAGED.value})

    async def _authenticate(*_: Any, **__: Any) -> Any:
        return SimpleNamespace(id="tablet", project_id=team.id)

    monkeypatch.setattr(_deps, "authenticate_device", _authenticate)

    captured: dict[str, Any] = {}

    async def _run_turn(**kwargs: Any) -> TurnOutcome:
        captured.update(kwargs)
        return TurnOutcome(speech="Vamos ficar no começo.", transcript="")

    async def _speech(text: str, **_: Any) -> tuple[SynthesizedSpeech, bool]:
        return SynthesizedSpeech(
            audio=b"audio", mime_type="audio/mpeg", etag="e", cached=False, key="tts/x.mp3"
        ), False

    monkeypatch.setattr(prepare_opening_module, "run_turn", _run_turn)
    monkeypatch.setattr(prepare_opening_module, "synthesize_facilitator_speech", _speech)

    async with _room_client(db_session) as client:
        created = await client.post(
            f"{IR}/sessions",
            headers={"X-Device-Credential": "tablet"},
            json={"pericope": "OV"},
        )
    assert created.status_code == 200, created.text[:200]

    assert captured["coverage_state"] == tuesday.coverage_state, (
        "a abertura preparada montava o LEDGER a partir de um {} literal, ignorando o colar "
        "que essa mesma equipe já carrega para a passagem"
    )
    assert "WORKED WITH BY THE TEAM (engaged):" in coverage_status_block(
        captured["coverage_state"], pericope
    )
