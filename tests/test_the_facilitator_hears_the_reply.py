"""ENG-1276 — «Ouvir a resposta»: the facilitator hears the reply they recorded.

The card of an answered question carries the address of its reply, and a route beside the
question's own hands the Desk a short-lived signed address for it. Both doors are followed to
the end and asserted on the bytes that arrive, never on the string that led there.
"""

from urllib.parse import urlencode

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ProjectRole
from app.db.models.internalization_room import IRQuestion, IRQuestionStatus, IRSession
from app.services.internalization_room import questions as service
from tests.baker import (
    a_language,
    grant_facilitator_app_role,
    make_project,
    make_project_user_access,
    make_user,
)

IR = "/api/internalization-room"
STORAGE = "/armazenamento"
BUCKET = "balde-de-teste"
FIRST = b"a primeira resposta, que a facilitadora gravou"
SECOND = b"a resposta corrigida, gravada depois"
BEFORE_THIS_CHANGE = b"uma resposta guardada antes desta mudanca"


class Bucket:
    def __init__(self, objects: dict[str, bytes]) -> None:
        self.objects = objects

    async def get(self, key: str) -> bytes | None:
        return self.objects.get(key)

    async def put(self, key: str, data: bytes, mime: str) -> None:
        self.objects[key] = data


@pytest.fixture()
def objects() -> dict[str, bytes]:
    return {}


@pytest.fixture()
async def client(db_session: AsyncSession, objects, monkeypatch: pytest.MonkeyPatch):
    from fastapi import FastAPI, Response

    from app.api.internalization_room import router
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import NotFoundError, register_exception_handlers

    monkeypatch.setattr(get_settings(), "gcs_platform_bucket", BUCKET, raising=False)
    monkeypatch.setattr(service, "_store", lambda *a, **kw: Bucket(objects))

    async def _signed(
        bucket: str, key: str, *, expiry_minutes: int, response_content_type: str | None = None
    ) -> str:
        window = urlencode({"X-Goog-Expires": expiry_minutes * 60})
        return f"http://test{STORAGE}/{bucket}/{key}?{window}"

    monkeypatch.setattr(service, "generate_signed_download_url", _signed)

    test_app = FastAPI()
    test_app.include_router(router, prefix=IR)

    @test_app.get(f"{STORAGE}/{{bucket}}/{{key:path}}", response_model=None)
    async def _bucket(bucket: str, key: str) -> Response:
        stored = objects.get(key)
        if bucket != BUCKET or stored is None:
            raise NotFoundError(f"no object at {key}")
        return Response(content=stored)

    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    async with httpx.AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as c:
        yield c


async def a_facilitator(db: AsyncSession, *, email: str):
    user = await make_user(db, email=email)
    language = await a_language(db, name=f"Lang {email}")
    project = await make_project(db, language.id, name=f"Team {email}")
    await make_project_user_access(db, project.id, user.id, role=ProjectRole.FACILITATOR)
    await grant_facilitator_app_role(db, user.id)

    from app.services.auth.issue_tokens import issue_tokens

    access, _refresh = await issue_tokens(db, user)
    return project, {"Authorization": f"Bearer {access}"}


async def an_open_question(db: AsyncSession, objects, project_id: str, *, tag: str) -> IRQuestion:
    key = f"internalization-room/questions/{tag}.m4a"
    objects[key] = b"a pergunta da equipe"
    session = IRSession(id=f"sessao-{tag}", pericope="P03", project_id=project_id)
    db.add(session)
    await db.flush()
    question = IRQuestion(
        id=f"pergunta-{tag}",
        session_id=session.id,
        device_id=f"tablet-{tag}",
        project_id=project_id,
        pericope="P03",
        status=IRQuestionStatus.OPEN,
        audio_key=key,
    )
    db.add(question)
    await db.commit()
    return question


async def answer(client, headers, question_id: str, audio: bytes) -> None:
    sent = await client.post(
        f"{IR}/facilitator/questions/{question_id}/reply",
        headers=headers,
        files={"file": ("resposta.m4a", audio, "audio/mp4")},
    )
    assert sent.status_code == 200, sent.text


def reply_route(question_id: str) -> str:
    return f"{IR}/facilitator/questions/{question_id}/reply/audio"


async def card_of(client, headers, question_id: str) -> dict:
    inbox = await client.get(f"{IR}/facilitator/questions", headers=headers)
    assert inbox.status_code == 200, inbox.text
    return next(card for card in inbox.json()["questions"] if card["question_id"] == question_id)


async def heard_through_the_route(client, headers, question_id: str) -> bytes:
    signed = await client.get(reply_route(question_id), headers=headers)
    assert signed.status_code == 200, signed.text
    played = await client.get(signed.json()["url"])
    assert played.status_code == 200, played.text[:200]
    return played.content


async def heard_through_the_card(client, headers, question_id: str) -> bytes:
    address = (await card_of(client, headers, question_id))["reply_audio_url"]
    played = await client.get(address, headers=headers)
    assert played.status_code == 200, played.text[:200]
    return played.content


async def test_an_answered_questions_card_carries_its_replys_audio(client, db_session, objects):
    project, headers = await a_facilitator(db_session, email="fac@example.com")
    open_question = await an_open_question(db_session, objects, project.id, tag="aberta")
    answered = await an_open_question(db_session, objects, project.id, tag="respondida")
    await answer(client, headers, answered.id, FIRST)

    assert (await card_of(client, headers, answered.id))["reply_audio_url"]
    assert (await card_of(client, headers, open_question.id))["reply_audio_url"] is None


async def test_ouvir_a_resposta_plays_the_facilitators_own_reply_as_stored(
    client, db_session, objects
):
    project, headers = await a_facilitator(db_session, email="fac@example.com")
    question = await an_open_question(db_session, objects, project.id, tag="ouvir")
    await answer(client, headers, question.id, FIRST)

    assert await heard_through_the_route(client, headers, question.id) == FIRST
    assert await heard_through_the_card(client, headers, question.id) == FIRST


async def test_a_re_recorded_reply_replaces_the_old_one_in_what_the_facilitator_hears(
    client, db_session, objects
):
    project, headers = await a_facilitator(db_session, email="fac@example.com")
    question = await an_open_question(db_session, objects, project.id, tag="corrigida")
    await answer(client, headers, question.id, FIRST)
    await answer(client, headers, question.id, SECOND)

    assert await heard_through_the_route(client, headers, question.id) == SECOND
    assert await heard_through_the_card(client, headers, question.id) == SECOND


async def test_a_question_with_no_reply_has_nothing_to_play(client, db_session, objects):
    project, headers = await a_facilitator(db_session, email="fac@example.com")
    question = await an_open_question(db_session, objects, project.id, tag="muda")

    refused = await client.get(reply_route(question.id), headers=headers)

    assert refused.status_code == 404
    assert "reply" in refused.text.lower()


async def test_a_facilitator_of_another_team_cannot_hear_the_reply(client, db_session, objects):
    project, headers = await a_facilitator(db_session, email="fac@example.com")
    _other, strangers = await a_facilitator(db_session, email="outra@example.com")
    question = await an_open_question(db_session, objects, project.id, tag="alheia")
    await answer(client, headers, question.id, FIRST)

    refused = await client.get(reply_route(question.id), headers=strangers)

    assert await heard_through_the_route(client, headers, question.id) == FIRST
    assert refused.status_code == 404


async def test_a_reply_stored_before_this_change_plays(client, db_session, objects):
    project, headers = await a_facilitator(db_session, email="fac@example.com")
    question = await an_open_question(db_session, objects, project.id, tag="antiga")
    key = f"internalization-room/questions/{question.id}/resposta-0123456789abcdef.m4a"
    objects[key] = BEFORE_THIS_CHANGE
    question.reply_audio_key = key
    question.status = IRQuestionStatus.ANSWERED
    await db_session.commit()

    assert (await card_of(client, headers, question.id))["reply_audio_url"]
    assert await heard_through_the_route(client, headers, question.id) == BEFORE_THIS_CHANGE
    assert await heard_through_the_card(client, headers, question.id) == BEFORE_THIS_CHANGE
