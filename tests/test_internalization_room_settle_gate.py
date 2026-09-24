"""Which turns reach the coverage classifier, and on whose silence they stop.

The gate used to read `used_fail_safe`, which is a fact about the Guide: it says the room
could not phrase a reply. Whether the team said anything is a different fact, and the
comprehension ledger already kept it — so a fail-safe landing on a credited answer threw
away the beads that answer had just earned (session 86a0cbbd, turn 15, the highest-value
element in P01).
"""

import json
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.internalization_room import background
from app.services.internalization_room.canon.elements import elements_for
from app.services.internalization_room.coverage import coverage_view
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.run_turn import TurnOutcome
from app.services.internalization_room.sessions import create_session, get_session

IR = "/api/internalization-room"
ROOM_KEY = "sala-de-teste"
TEAM = "A fome grande fez a família se mudar."
FAIL_SAFE = "Tem bastante coisa aqui. Vamos com calma e ficar nesta cena."
OPENING = "Vamos ficar no começo: uma família sai de Belém por falta de comida."
INAUDIBLE = "Não consegui ouvir. Podem repetir mais perto do microfone?"
MOTHER_TONGUE_NOTE = (
    "[A equipe falou na língua materna por cerca de 12 segundos; sem transcrição — nenhuma "
    "palavra chegou até você.]"
)


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

        async def _comprehension_turn(*_: Any, **__: Any) -> TurnOutcome:
            return staged.outcome

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


async def test_an_opening_is_classified_once_as_the_turn_the_team_has_not_spoken_in_yet(
    room: _Room, passage: str
) -> None:
    """Her route classifies every turn that is not a panorama, the kickoff included
    (`route.ts:179,185-194`). The opening names beads from the Guide's side alone, which her
    classifier may only mark `surfaced`; the team's necklace counts `engaged`, so the opening
    reaches the Guide's ledger and the Desk and leaves the team's screen as it was."""
    room.outcome = TurnOutcome(speech=OPENING, transcript="")

    await _the_room_opens(room, passage)

    assert [
        (handed["team_utterance"], handed["guide_response"], handed["opening"])
        for handed in room.settled
    ] == [("", OPENING, True)], (
        "a abertura nunca chegava ao classificador, e o que o Guia levantou nela não ficava "
        "registrado como levantado"
    )


async def test_a_turn_nobody_could_be_heard_in_is_classified_with_an_empty_slot(
    room: _Room, passage: str
) -> None:
    """An inaudible answer is not the opening it resembles: the team spoke and the room did
    not catch it. Her classifier is handed what reached the Guide as the team's turn, and on an
    empty take that is nothing (`oralTurn.ts:70`) — never the opening's placeholder."""
    room.outcome = TurnOutcome(speech=OPENING, transcript="")
    await _the_room_opens(room, passage)
    room.outcome = TurnOutcome(speech=INAUDIBLE, transcript="", used_fail_safe=True, degraded=True)

    await _the_team_answers(room, passage)

    assert [
        (handed["team_utterance"], handed["guide_response"], handed["opening"])
        for handed in room.settled
    ] == [("", OPENING, True), ("", INAUDIBLE, False)], (
        "o turno inaudível ficava fora do classificador, ou chegava a ele como se fosse a abertura"
    )


async def test_an_opening_the_room_could_not_phrase_is_still_classified_as_the_opening(
    room: _Room, passage: str
) -> None:
    """Her route classifies the kickoff with no condition on how the Guide's line came out.
    A fail-safe line names nothing, so the classifier moves nothing on it."""
    room.outcome = TurnOutcome(speech=FAIL_SAFE, transcript="", used_fail_safe=True, degraded=True)

    await _the_room_opens(room, passage)

    assert [(handed["guide_response"], handed["opening"]) for handed in room.settled] == [
        (FAIL_SAFE, True)
    ], "a abertura em fail-safe ficava fora do classificador, ao contrário da rota dela"


async def test_a_take_with_no_words_is_classified_with_an_empty_slot(
    room: _Room, passage: str
) -> None:
    """The room asks the team to say it again, so the classifier reads the Guide's request
    and an empty team slot — nothing it could credit an `engaged` bead to."""
    room.outcome = TurnOutcome(speech=INAUDIBLE, transcript="", used_fail_safe=True, degraded=True)
    room.heard = HeardSpeech()

    await _the_team_answers(room, passage)

    assert [(handed["team_utterance"], handed["guide_response"]) for handed in room.settled] == [
        ("", INAUDIBLE)
    ], "o turno sem palavras ficava fora do classificador"


async def test_an_answer_in_the_mother_tongue_is_classified_with_the_note_the_guide_read(
    room: _Room, passage: str
) -> None:
    """On a mother-tongue take her classifier reads the room-note, which is what reached the
    Guide as the team's turn (`oralTurn.ts:14,92`); the transcript is empty on that turn."""
    room.outcome = TurnOutcome(speech=OPENING, transcript="", room_note=MOTHER_TONGUE_NOTE)
    room.heard = HeardSpeech(text=TEAM, language_code="ter", language_probability=0.99)

    await _the_team_answers(room, passage)

    assert [handed["team_utterance"] for handed in room.settled] == [MOTHER_TONGUE_NOTE], (
        "a fala na língua materna ficava fora do classificador, e a nota que o Guia leu "
        "nunca chegava a ele"
    )


async def test_a_team_walking_back_in_hears_the_line_again_and_nothing_is_classified_twice(
    room: _Room, passage: str
) -> None:
    """Every turn that appends an exchange is classified once; "say it again" appends none,
    so the opening it repeats is not handed to the classifier a second time."""
    room.outcome = TurnOutcome(speech=OPENING, transcript="")
    await _the_room_opens(room, passage)

    back = await _the_room_opens(room, passage)

    assert [handed["guide_response"] for handed in room.settled] == [OPENING], (
        "a equipe que voltava à passagem reclassificava a abertura que só ouviu de novo"
    )
    assert back.json()["classification_pending"] is False


@asynccontextmanager
async def _handed(db_session: AsyncSession) -> AsyncIterator[AsyncSession]:
    yield db_session


async def test_an_opening_naming_the_arc_and_the_tone_leaves_them_surfaced_and_nothing_engaged(
    room: _Room, passage: str, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Her classifier marks `surfaced` from the Guide alone and `engaged` only from the team
    (`classifier_system_prompt.md:47-48,56-58`), and the team's necklace counts `engaged`
    (`colar_overlay.dart:84`): the opening moves the Guide's ledger and the Desk, and the
    team's screen stays where it was until the team speaks."""
    from app.api.internalization_room import sessions as sessions_api

    named = [
        element.key for element in elements_for("P01") if element.kind.value in {"arc", "tone"}
    ]
    shown: list[str] = []

    async def _her_classifier(*, system_prompt: str, **_: Any) -> str:
        shown.append(system_prompt)
        return json.dumps(
            {
                "decisions": [
                    {"element_id": key, "new_status": "surfaced", "evidence": "o Guia nomeou"}
                    for key in named
                ]
            }
        )

    monkeypatch.setattr(sessions_api, "settle_coverage", background.settle_coverage)
    monkeypatch.setattr(background, "AsyncSessionLocal", lambda: _handed(db_session))
    monkeypatch.setattr(
        sys.modules["app.services.internalization_room.classify_coverage"],
        "call_agent",
        _her_classifier,
    )
    room.outcome = TurnOutcome(speech=OPENING, transcript="")

    await _the_room_opens(room, passage)

    view = coverage_view(await get_session(db_session, passage))
    assert len(named) == 2
    assert (view.surfaced, view.engaged) == (2, 0), (
        "o que o Guia levantou na abertura não ficava registrado como levantado, e os eixos "
        "do nível 1 só chegavam à barra do piso em turnos posteriores"
    )
    assert "(the team has not spoken yet)" in shown[0], (
        "a abertura chegava ao classificador com o slot da equipe vazio, como um turno em que "
        "a equipe falou e não foi ouvida"
    )


async def test_an_opening_promises_its_classification_under_the_turn_it_settles(
    room: _Room, passage: str
) -> None:
    """The app arms its wait for the settled frame only on the response's word, so an opening
    the classifier now reads has to say so, under the turn id the frame will carry."""
    room.outcome = TurnOutcome(speech=OPENING, transcript="")

    opened = await _the_room_opens(room, passage)

    assert opened.json()["classification_pending"] is True, (
        "a abertura ia ao classificador sem que a resposta dissesse que ele corria"
    )
    assert opened.json()["turn_id"] == room.settled[0]["turn_id"] != ""


async def test_an_answer_the_classifier_will_read_is_promised_under_the_turn_it_settles(
    room: _Room, passage: str
) -> None:
    """The response names the turn, and the classifier is handed that same name, so the
    frame the channel carries later can be matched to the turn the app is waiting on."""
    room.outcome = TurnOutcome(speech=OPENING, transcript=TEAM)

    answered = await _the_team_answers(room, passage)

    assert answered.json()["classification_pending"] is True, (
        "a fala da equipe ia ao classificador sem que a resposta dissesse que ele corria"
    )
    assert answered.json()["turn_id"] == room.settled[0]["turn_id"] != "", (
        "a resposta e o classificador não partilhavam um nome de turno, e o app não "
        "tinha como saber de qual turno era a cobertura que chegava"
    )


async def test_a_panorama_answer_is_heard_but_promises_no_classification(
    room: _Room, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A panorama has no coverage spine, so the gate lets the team's words through and the
    settle hands them to nobody — and the response has to say that, not the gate's yes."""
    from app.api.internalization_room import sessions as sessions_api

    async def _panorama_turn(*_: Any, **__: Any) -> TurnOutcome:
        return room.outcome

    monkeypatch.setattr(sessions_api.room, "run_panorama_turn", _panorama_turn)
    panorama = await create_session(db_session, pericope="OV-Ruth", language="pt")
    room.outcome = TurnOutcome(speech=OPENING, transcript=TEAM)

    answered = await _the_team_answers(room, panorama.id)

    assert room.settled == []
    assert answered.json()["classification_pending"] is False, (
        "o portão dizia sim à fala da equipe e o panorama descartava o settle em silêncio, "
        "então a resposta prometia uma cobertura que nunca viria"
    )
