"""Which turns reach the coverage classifier, and on whose silence they stop.

The gate used to read `used_fail_safe`, which is a fact about the Guide: it says the room
could not phrase a reply. Whether the team said anything is a different fact, and the
comprehension ledger already kept it — so a fail-safe landing on a credited answer threw
away the beads that answer had just earned (session 86a0cbbd, turn 15, the highest-value
element in P01).
"""

from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.run_turn import TurnOutcome
from app.services.internalization_room.sessions import create_session

IR = "/api/internalization-room"
ROOM_KEY = "sala-de-teste"
TEAM = "A fome grande fez a família se mudar."
FAIL_SAFE = "Tem bastante coisa aqui. Vamos com calma e ficar nesta cena."
OPENING = "Vamos ficar no começo: uma família sai de Belém por falta de comida."
INAUDIBLE = "Não consegui ouvir. Podem repetir mais perto do microfone?"
OFF_BRIDGE = "Podemos continuar na língua da sessão?"


@dataclass
class _Room:
    """The endpoint, the turn it will decide, and what the classifier was handed."""

    client: httpx.AsyncClient
    outcome: TurnOutcome
    heard: HeardSpeech | None = None
    settled: list[dict[str, str]] = field(default_factory=list)


@pytest.fixture()
async def room(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    """The room over HTTP with the turn already decided.

    The question here is what the router does with an outcome, not how the Guide arrived at
    one, so the turn is handed in whole and the classifier is a list.
    """
    from fastapi import FastAPI
    from httpx import ASGITransport

    from app.api.internalization_room import router as room_router
    from app.api.internalization_room import sessions as sessions_api
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers
    from app.services.internalization_room.comprehension.state import ComprehensionState
    from app.services.internalization_room.live_turn import ComprehensionTurn
    from app.services.platform.tts import SynthesizedSpeech

    monkeypatch.setattr(get_settings(), "internalization_room_api_key", ROOM_KEY, raising=False)

    test_app = FastAPI()
    test_app.include_router(room_router, prefix=IR)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        staged = _Room(client=c, outcome=TurnOutcome(speech=OPENING, transcript=""))

        async def _comprehension_turn(*_: Any, **__: Any) -> ComprehensionTurn:
            return ComprehensionTurn(outcome=staged.outcome, state=ComprehensionState())

        async def _heard(*_: Any, **__: Any) -> HeardSpeech:
            return staged.heard or HeardSpeech(text=staged.outcome.transcript)

        async def _speech(text: str, **_: Any) -> tuple[SynthesizedSpeech, bool]:
            return SynthesizedSpeech(
                audio=b"audio",
                mime_type="audio/mpeg",
                etag="e",
                cached=False,
                key="tts/voice/m/f/line.mp3",
            ), False

        async def _record(**handed: str) -> None:
            staged.settled.append(handed)

        monkeypatch.setattr(sessions_api.room, "run_comprehension_turn", _comprehension_turn)
        monkeypatch.setattr(sessions_api.room, "synthesize_facilitator_speech", _speech)
        monkeypatch.setattr(sessions_api, "heard_speech", _heard)
        monkeypatch.setattr(sessions_api, "settle_coverage", _record)

        yield staged


@pytest.fixture()
async def passage(db_session: AsyncSession) -> str:
    """A passage session with nothing prepared, so every opening here is written on demand."""
    session = await create_session(db_session, pericope="P01", language="pt")
    return session.id


async def _the_room_opens(room: _Room, session_id: str) -> httpx.Response:
    opened = await room.client.post(
        f"{IR}/sessions/{session_id}/turns", headers={"X-Room-Key": ROOM_KEY}
    )
    assert opened.status_code == 200, opened.text[:200]
    return opened


async def _the_team_answers(room: _Room, session_id: str) -> httpx.Response:
    answered = await room.client.post(
        f"{IR}/sessions/{session_id}/turns",
        headers={"X-Room-Key": ROOM_KEY},
        files={"file": ("answer.m4a", b"audio", "audio/m4a")},
    )
    assert answered.status_code == 200, answered.text[:200]
    return answered


@pytest.mark.asyncio
async def test_a_fail_safe_still_hands_over_what_the_team_said(room: _Room, passage: str) -> None:
    """The Guide having nothing sayable is not evidence that the team said nothing.

    The fail-safe line carries no content of its own, so the classifier simply reads a turn
    whose Guide side surfaces nothing — while the team's own words, which the comprehension
    ledger had already credited, still reach the necklace.
    """
    room.outcome = TurnOutcome(
        speech=FAIL_SAFE, transcript=TEAM, used_fail_safe=True, degraded=True
    )

    await _the_team_answers(room, passage)

    assert [handed["team_utterance"] for handed in room.settled] == [TEAM], (
        "o turno em fail-safe apagava a fala da equipe, e as contas que ela nomeou "
        "ficavam por creditar sem que nada dissesse"
    )


@pytest.mark.asyncio
async def test_an_opening_names_beads_the_team_never_spoke_toward_and_settles_none_of_them(
    room: _Room, passage: str
) -> None:
    """The turn that used to earn an exception for carrying no utterance at all.

    An opening lays the scene out and names around ten map elements from the Guide's side
    alone, with nothing from the team behind any of them. Coverage is `engaged`-only on the
    team's screen now, so a sentence the room wrote for itself is not evidence of anything
    the team heard, and the gate reads an opening the same way it reads any other turn with
    nothing said into it.
    """
    room.outcome = TurnOutcome(speech=OPENING, transcript="")

    await _the_room_opens(room, passage)

    assert room.settled == [], (
        "a abertura escrita na hora nomeava contas sem que a equipe tivesse dito nada, e "
        "coverage passou a ser engaged-only na tela do time"
    )


@pytest.mark.asyncio
async def test_a_turn_nobody_could_be_heard_in_is_not_settled(room: _Room, passage: str) -> None:
    """An inaudible answer is not the opening it resembles, and settles no more than it did.

    An inaudible answer reaches the gate looking like an opening — an empty utterance and a
    fail-safe line — and it is not one: the team spoke, the room simply did not catch it.
    Neither turn here carries anything the team said, and neither reaches the classifier.
    """
    room.outcome = TurnOutcome(speech=OPENING, transcript="")
    await _the_room_opens(room, passage)
    room.outcome = TurnOutcome(speech=INAUDIBLE, transcript="", used_fail_safe=True, degraded=True)

    await _the_team_answers(room, passage)

    assert room.settled == [], (
        "nem a abertura nem um turno inaudível carregam fala da equipe, e nenhum dos dois "
        "deveria chegar ao classificador"
    )


@pytest.mark.asyncio
async def test_an_opening_the_room_could_not_phrase_hands_over_nothing(
    room: _Room, passage: str
) -> None:
    """A fail-safe opening is a contentless line, not evidence of anything, opening or not.

    Redrafting runs out on the first turn like any other, so a fail-safe opening is a line
    the room reaches for when it has nothing to say — `prepare_opening` throws exactly this
    away rather than keep it. No turn with an empty transcript settles any more, so this one
    needs no opening-specific reasoning to stay out of the classifier's hands.
    """
    room.outcome = TurnOutcome(speech=FAIL_SAFE, transcript="", used_fail_safe=True, degraded=True)

    await _the_room_opens(room, passage)

    assert room.settled == [], (
        "a abertura em fail-safe entregava ao classificador a mesma linha fixa que o "
        "turno inaudível tem de manter longe dele"
    )


@pytest.mark.asyncio
async def test_a_transcript_the_hearing_does_not_trust_hands_over_nothing(
    room: _Room, passage: str
) -> None:
    """Words the room is about to ask the team to repeat are not words to credit beads to.

    `uncertain` exists to under-count and nothing else — an uncertain transcript is repeated,
    never judged as misunderstanding (`HeardSpeech`). It reaches the gate looking like an
    answer, because the inaudible outcome carries the transcript forward while the team hears
    a request to say it again. Coverage only moves forward and feeds the Guide's next prompt,
    so a bead settled on a word the hearing distrusts cannot be taken back.
    """
    room.outcome = TurnOutcome(
        speech=INAUDIBLE, transcript=TEAM, used_fail_safe=True, degraded=True
    )
    room.heard = HeardSpeech(text=TEAM, transcript_confidence=0.2)

    await _the_team_answers(room, passage)

    assert room.settled == [], (
        "a cobertura era creditada em cima de palavras que o próprio STT marcou como "
        "não confiáveis, enquanto a equipe ouvia um pedido para repetir"
    )


@pytest.mark.asyncio
async def test_an_answer_left_in_another_language_hands_over_nothing(
    room: _Room, passage: str
) -> None:
    """The room asked for the session's language back; it did not take the answer up.

    Mother-tongue speech is not distrusted the way an uncertain transcript is — it is heard
    perfectly well and left unengaged, and the team hears the off-bridge fixed line rather
    than a reply. Settling it would credit beads read against a meaning map in one language
    from an utterance in another, on a turn the room declined, and coverage does not come
    back down.
    """
    room.outcome = TurnOutcome(
        speech=OFF_BRIDGE, transcript=TEAM, used_fail_safe=True, fixed_line="off_bridge"
    )
    room.heard = HeardSpeech(
        text=TEAM, language_code="ter", language_probability=0.99, transcript_confidence=0.9
    )

    await _the_team_answers(room, passage)

    assert room.settled == [], (
        "a fala que ficou em outra língua era creditada sem tradução, num turno em que "
        "a sala pediu para repetir na língua da sessão"
    )
