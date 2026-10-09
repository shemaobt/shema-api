"""ENG-447 — a question's transcript is the facilitator's, and the room app never reads it.

Transcribing the team's questions *for the team* is out of scope for v1 on purpose: the
team's voice stays voice. The transcript exists so the inbox can be skimmed, and so the set
of them becomes the log of questions the Meaning Map could not answer — both of which happen
on the facilitator's side of the wall.

So the guarantee has to be about **the set of routes the room app can reach**, not about the
one route that carries the field today. A promise kept by remembering to leave a field out of
each new schema is a promise the next route breaks. Everything below is derived from the
mounted application, so a route that would break it fails this file on the day it is written:

* which routes the room app reaches — every mounted route whose dependency tree, or whose own
  body, calls the tablet's gates (`require_room_caller`, `require_device`) — shared with the
  credential audit as `room_route_audit_harness.room_app_routes` (ENG-1039), so a route gated
  by hand instead of by `Depends` cannot go unaudited in one file and not the other;
* which of those can reach a question — the ones the room's question router mounts, read off
  the module rather than listed here, so a fourth one is covered the day it is added;
* what a route can put in a body — every model reachable from the return type FastAPI
  resolved, read recursively.

**On the word "transcript" appearing elsewhere.** `TurnResponse.transcript`, the team's own
utterance in a turn of the conversation with the guide, is gone from the tablet's answer
(ENG-1335); `test_ir_the_tablet_never_receives_the_teams_words.py` holds that over every door.
This file keeps asking the narrower question about a *question's* transcript.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRQuestion, IRQuestionStatus, IRSession
from app.models.internalization_room import InboxQuestionView
from app.services.internalization_room import questions as service
from app.services.internalization_room.voice_handles import to_handle
from tests.device_harness import TABLET_TEAM, a_linked_tablet
from tests.room_route_audit_harness import models_in, named, room_app_routes

#: How the facilitator's card spells the two fields that must never travel together to the
#: room. Read off the card rather than typed here, so a rename that keeps the leak takes this
#: audit with it — and read off the *card* rather than the column, because what a response
#: names is what a client can read.
QUESTION_IDENTITY = "question_id"
TRANSCRIPT_FIELD = IRQuestion.transcript.key

assert {QUESTION_IDENTITY, TRANSCRIPT_FIELD} <= set(InboxQuestionView.model_fields), (
    "o cartao do facilitador deixou de nomear a pergunta ou a transcricao, entao esta "
    "auditoria esta procurando por uma forma que nao existe mais"
)

#: What a question's transcript says in this file. Unmistakable in a response body, and
#: nothing else in the room could produce it.
SENTINEL = "SENTINELA-TRANSCRICAO-QUE-NAO-PODE-SAIR-DA-MESA"

FIXTURE = Path(__file__).parent / "fixtures" / "pergunta-1500ms.m4a"
DEVICE = "tablet-da-equipe-1"
SESSION = "sessao-1"


def question_routes_the_room_reaches() -> list:
    """The room routes that can reach an ``IRQuestion`` at all.

    Taken from the question router's own endpoints rather than from a list of paths: a
    fourth question route is then covered by this file the moment it is mounted, which is
    the point — the route nobody remembered is the one that leaks.
    """
    from app.api.internalization_room import questions as questions_api

    mounted = {route.endpoint for route in questions_api.router.routes}
    return [route for route in room_app_routes() if route.endpoint in mounted]


def test_no_route_the_room_reaches_serves_a_question_beside_its_transcript() -> None:
    """The structural half, over every route the tablet can call.

    The shape looked for is a response that names a question *and* carries a transcript,
    because that is what the leak would be: the facilitator's card, or something built like
    it, handed to the room. A schema that carried only one of the two says nothing about a
    question the team asked.
    """
    leaking = {
        named(route): model.__name__
        for route in room_app_routes()
        for model in models_in(route.response_model)
        if {QUESTION_IDENTITY, TRANSCRIPT_FIELD} <= set(model.model_fields)
    }

    assert not leaking, (
        "estas rotas da sala devolvem a transcricao de uma pergunta, que e do facilitador "
        f"e so dele: {leaking}"
    )


def test_every_question_route_the_room_reaches_is_exercised() -> None:
    """Nothing escapes the sentinel by being added after this file was written."""
    reachable = {named(route) for route in question_routes_the_room_reaches()}

    assert reachable == set(EXERCISED), (
        "as rotas de pergunta que a sala alcanca mudaram; a garantia so vale sobre as que "
        f"sao exercidas de fato — faltam {sorted(reachable - set(EXERCISED))}, sobram "
        f"{sorted(set(EXERCISED) - reachable)}"
    )


#: One request per room route that can reach a question, shaped well enough to get a body
#: back. `{question_id}` stands for the question this file plants the sentinel on.
EXERCISED: dict[tuple[str, str], dict] = {
    ("POST", "/api/internalization-room/questions"): {
        "params": {"session_id": SESSION},
        "files": {"file": ("pergunta.m4a", FIXTURE.read_bytes(), "audio/mp4")},
    },
    ("GET", "/api/internalization-room/questions/replies"): {},
    ("POST", "/api/internalization-room/questions/{question_id}/heard"): {},
    #: `{handle}` stands for the reply this file hangs on the question, the same way
    #: `{question_id}` stands for the question. The route serves bytes rather than a card,
    #: which is exactly why it belongs here: a route nobody exercises is a route the audit
    #: below cannot speak for, whatever it happens to return.
    ("GET", "/api/internalization-room/questions/audio/{handle}"): {},
}


class MemoryStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def get(self, key: str) -> bytes | None:
        return self.objects.get(key)

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = data


@pytest.fixture()
async def room_client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    """The room's own router, gated exactly as the tablet meets it.

    The store and the transcriber are the two machines outside this process, and both are
    replaced — the second one by something that returns the sentinel, so that every question
    raised through this client is one whose transcript would be visible if it could travel.
    """
    from app.api.internalization_room.questions import router as questions_router
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    store = MemoryStore()

    async def stt(audio: bytes, *, language: str, mime_type: str) -> str:
        return SENTINEL

    monkeypatch.setattr(service, "_store", lambda *a, **kw: store)
    monkeypatch.setattr(service, "transcribe_speech", stt)

    test_app = FastAPI()
    test_app.include_router(questions_router, prefix="/api/internalization-room")
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    tablet = await a_linked_tablet(db_session, team_id=TABLET_TEAM)
    async with httpx.AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://test",
        headers=tablet.headers | {"X-Room-Device": DEVICE},
    ) as client:
        yield client


async def a_question_the_room_could_read_back(db: AsyncSession, room_client) -> IRQuestion:
    """A question of this device, transcribed, answered, and waiting to be collected.

    Answered on purpose: an open question is invisible to `replies`, so a sentinel test run
    against one would pass without the route ever having had the chance to leak.
    """
    db.add(IRSession(id=SESSION, pericope="P03"))
    await db.commit()

    raised = await room_client.post(
        "/api/internalization-room/questions",
        **EXERCISED[("POST", "/api/internalization-room/questions")],
    )
    assert raised.status_code == 200, raised.text

    question = await service.get_question(db, raised.json()["question_id"])
    assert question.transcript == SENTINEL, "o cenario nao provou nada: nada foi transcrito"

    question.status = IRQuestionStatus.ANSWERED
    question.reply_audio_key = "internalization-room/questions/resposta.m4a"
    await service._store().put(question.reply_audio_key, b"resposta falada", "audio/mp4")
    await db.commit()
    return question


async def test_the_room_never_reads_back_the_transcript_of_its_own_question(
    db_session: AsyncSession, room_client
) -> None:
    """The behavioural half: every room route that touches a question, asked for real."""
    from app.services.internalization_room.questions import get_question

    question = await a_question_the_room_could_read_back(db_session, room_client)

    for (method, path), request in EXERCISED.items():
        url = path.replace("{question_id}", question.id).replace(
            "{handle}", to_handle(question.reply_audio_key or "")
        )
        answer = await room_client.request(method, url, **request)

        assert answer.status_code == 200, f"{method} {url}: {answer.text}"
        assert SENTINEL not in answer.text, f"{method} {path} devolveu a transcricao"

    assert (await get_question(db_session, question.id)).transcript == SENTINEL, (
        "a transcricao sumiu no meio do teste, entao as rotas acima nao tinham o que vazar"
    )
