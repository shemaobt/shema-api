"""The demolition guard for the method question and the mode that followed it.

A team opened a session and the first thing it heard was the app: the Guide's opening with
a fixed method-choice question welded onto the end, and then a whole turn answered by a
regex parser instead of by the Guide. What the parser decided was written onto the session
row, said back to the tablet, posted again on the next `createSession`, and read into the
Guide's own prompt every turn after that.

These tests describe absence. The parser they replace exercised nine pattern families and
three languages of a menu nobody is offered any more; what stands in its place has to hold
the four places the mechanism could come back — the opening the team hears, the turn after
it, the wire the tablet talks over, and the label the Validator reads the evidence by. The
fifth is the doctrine guard, which is the room's own oracle for "nothing stores a mode".
"""

from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.run_turn import TurnOutcome
from app.services.platform.tts import SynthesizedSpeech

PREFIX = "/api/internalization-room"
KEY = "sala-de-teste"
PANORAMA = "OV"
THE_TEAM_ANSWERS = "Uma pergunta curta de cada vez."
PASSAGE = "P03"
#: The method question as the ticket quotes it, in the three languages the room claims.
#: Read from the ticket rather than from `bridge_calibration_question`, which this branch
#: deletes: an expectation taken from the code under test agrees with it by construction.
THE_METHOD_QUESTION = {
    "pt": (
        "Quando trabalharmos as passagens, qual jeito fica melhor para vocês: "
        "contar naturalmente em português ou receber uma pergunta curta de cada vez?"
    ),
    "en": (
        "When we work through the passages, which suits you better: "
        "telling it back in your own words, or one short question at a time?"
    ),
    "es": (
        "Cuando trabajemos los pasajes, ¿qué les queda mejor: "
        "contarlo con sus propias palabras, o recibir una pregunta corta a la vez?"
    ),
}

GUIDE_OPENING = "Bem-vindos. Vamos conhecer o livro inteiro antes de entrar nele."
GUIDE_REPLY = "O livro começa numa fome, e uma família sai de casa por causa dela."


@pytest.fixture()
async def spoken(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    """A room whose every synthesized line is kept, so a test can read what was said.

    The method question is appended in the router, after the panorama turn has already
    returned, so no service seam can see it. What reaches the voice is the whole of it.

    `heard` is the other half: what the Guide was handed. A turn the app answers by
    itself never reaches the Guide at all, and an empty `heard` is how that shows.
    """
    from fastapi import FastAPI

    from app.api.internalization_room import router
    from app.api.internalization_room import sessions as sessions_api
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    monkeypatch.setattr(get_settings(), "internalization_room_api_key", KEY, raising=False)
    said: list[str] = []
    heard: list[str] = []

    async def _panorama(**handed: Any) -> TurnOutcome:
        heard.append(str(handed["transcript"]))
        return TurnOutcome(
            speech=GUIDE_OPENING if handed["opening"] else GUIDE_REPLY,
            transcript=str(handed["transcript"]),
            used_fail_safe=False,
        )

    async def _heard_speech(*_: Any, **__: Any) -> HeardSpeech:
        return HeardSpeech(text=THE_TEAM_ANSWERS, language_code="pt", transcript_confidence=0.99)

    async def _speech(text: str, **_: object) -> tuple[SynthesizedSpeech, bool]:
        said.append(text)
        entry = SynthesizedSpeech(
            audio=b"audio",
            mime_type="audio/mpeg",
            etag="e",
            cached=False,
            key=f"tts/voice/m/f/{abs(hash(text))}.mp3",
        )
        return entry, False

    async def _nothing(*_: Any, **__: Any) -> None:
        return None

    monkeypatch.setattr(sessions_api.room, "run_panorama_turn", _panorama)
    monkeypatch.setattr(sessions_api.room, "synthesize_facilitator_speech", _speech)
    monkeypatch.setattr(sessions_api, "prepare_opening", _nothing)
    monkeypatch.setattr(sessions_api, "settle_coverage", _nothing)
    monkeypatch.setattr(sessions_api, "heard_speech", _heard_speech)

    test_app = FastAPI()
    test_app.include_router(router, prefix=PREFIX)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, said, heard


async def _open_cold(client: httpx.AsyncClient, *, pericope: str, language: str) -> str:
    created = await client.post(
        f"{PREFIX}/sessions",
        headers={"X-Room-Key": KEY},
        json={"pericope": pericope, "language": language},
    )
    assert created.status_code == 200, created.text[:200]
    return str(created.json()["session_id"])


async def test_the_opening_is_the_guides_own_words_from_first_syllable_to_last(
    spoken: tuple[httpx.AsyncClient, list[str], list[str]],
) -> None:
    client, said, _ = spoken
    session_id = await _open_cold(client, pericope=PANORAMA, language="pt")

    opened = await client.post(f"{PREFIX}/sessions/{session_id}/turns", headers={"X-Room-Key": KEY})

    assert opened.status_code == 200, opened.text[:200]
    assert said == [GUIDE_OPENING], (
        "a sala grampeava a pergunta de método no fim da abertura e mandava o texto "
        f"emendado para a voz — a equipe ouvia {said}"
    )


async def test_the_teams_first_utterance_is_a_turn_like_any_other(
    spoken: tuple[httpx.AsyncClient, list[str], list[str]],
) -> None:
    client, said, heard = spoken
    session_id = await _open_cold(client, pericope=PANORAMA, language="pt")
    await client.post(f"{PREFIX}/sessions/{session_id}/turns", headers={"X-Room-Key": KEY})

    answered = await client.post(
        f"{PREFIX}/sessions/{session_id}/turns",
        headers={"X-Room-Key": KEY},
        files={"file": ("resposta.m4a", b"audio", "audio/m4a")},
    )

    assert answered.status_code == 200, answered.text[:200]
    assert heard == ["", THE_TEAM_ANSWERS], (
        "a resposta da equipe era lida por um parser de regex e o Guia nem era chamado — "
        f"chegou nele {heard}"
    )
    assert said[-1] == GUIDE_REPLY, (
        "a sala respondia com uma das nove falas fixas de reconhecimento, escolhida pelo "
        f"modo que o parser tinha acabado de decidir — a equipe ouviu {said[-1]!r}"
    )


async def test_a_mode_named_by_the_tablet_is_taken_in_and_never_said_back(
    spoken: tuple[httpx.AsyncClient, list[str], list[str]],
) -> None:
    client, _, _ = spoken
    created = await client.post(
        f"{PREFIX}/sessions",
        headers={"X-Room-Key": KEY},
        json={"pericope": PANORAMA, "language": "pt", "bridge_mode": "guided_microchecks"},
    )

    assert created.status_code == 200, (
        "o app do piloto ainda manda o modo no createSession, e recusar a chave deixa a "
        f"equipe sem sessão nenhuma — veio {created.status_code}: {created.text[:200]}"
    )
    session_id = created.json()["session_id"]
    turned = await client.post(f"{PREFIX}/sessions/{session_id}/turns", headers={"X-Room-Key": KEY})

    assert "bridge_mode" not in created.json(), (
        "a sala devolvia o modo ao tablet, que o guardava e o mandava de volta na sessão "
        f"seguinte — era assim que um modo atravessava sessões: {created.json()}"
    )
    assert "bridge_mode" not in turned.json(), (
        f"o turno também dizia o modo de volta, a cada turno: {turned.json()}"
    )


def test_no_file_the_doctrine_guard_reads_names_a_bridge_language_mode() -> None:
    """The room's own oracle for "nothing chooses, stores or inherits a mode".

    Marcia's guard greps `guided_microchecks|full_retell` in TypeScript and our backend is
    Python, so this rule of hers had nothing scanning it here until the Python guard was
    written. Its allowlist named every site the removal ladder had not reached yet; this
    ticket is the one that empties the mode half of it.
    """
    from scripts.check_doctrine import Rule, scan

    named = [f"{hit.file}:{hit.line} {hit.text}" for hit in scan() if hit.rule is Rule.MODE]

    assert named == [], f"a bridge-language mode is still named in the voice path: {named}"
