"""Whether a facilitator can press play on a raised hand and hear it.

The only assertion this path ever had was that the queue's address started with a route's
prefix. A prefix is not a recording: that check passed for months while the address behind
it answered 404. So these go over HTTP and assert the bytes that reach the browser,
following the redirect the way a browser follows it.
"""

from __future__ import annotations

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import select

from app.db.models.auth import Role
from app.db.models.internalization_room import IRSession
from app.services.internalization_room import questions as service
from app.services.platform.storage import StoredObject
from tests.baker import make_app, make_role, make_user, make_user_app_role

APP_KEY = "internalization-room"
IR = "/api/internalization-room"
BUCKET = "balde-de-teste"
STORAGE = "/balde-falso"
AUDIO = b"a equipe levantou a mao e perguntou isto"


class MemoryStore:
    """Where the room's audio lands, without a bucket."""

    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}

    async def get(self, key: str) -> bytes | None:
        stored = self.objects.get(key)
        return stored[0] if stored else None

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = (data, content_type)

    async def stat(self, key: str) -> StoredObject | None:
        return None


@pytest.fixture()
def store() -> MemoryStore:
    return MemoryStore()


@pytest.fixture()
async def room_app(db_session):
    app = await make_app(db_session, app_key=APP_KEY, name="Internalization Room")
    await make_role(db_session, app.id, role_key="facilitator", label="Facilitator", is_system=True)
    return app


@pytest.fixture()
async def settings(monkeypatch):
    from app.core.config import get_settings

    cfg = get_settings()
    monkeypatch.setattr(cfg, "gcs_platform_bucket", BUCKET, raising=False)
    return cfg


@pytest.fixture()
async def client(db_session, store, settings, monkeypatch):
    """The room's routes, plus an endpoint standing in for signed storage.

    The route answers with a redirect, so a test that stops at the redirect target proves
    nothing about the bytes. Storage is stubbed as an HTTP endpoint rather than as a return
    value, which is what lets the request be followed to the end. The stub honours
    `response-content-type` because the bucket honours it: that parameter is how the
    browser learns what it is about to play.
    """
    from fastapi import FastAPI, Response

    from app.api.internalization_room import router as room_router
    from app.core.database import get_db
    from app.core.exceptions import NotFoundError, register_exception_handlers

    async def _signed(
        bucket: str,
        key: str,
        *,
        expiry_minutes: int,
        response_content_type: str | None = None,
    ) -> str:
        query = f"?response-content-type={response_content_type}" if response_content_type else ""
        return f"http://test{STORAGE}/{bucket}/{key}{query}"

    monkeypatch.setattr(service, "generate_signed_download_url", _signed)

    test_app = FastAPI()
    test_app.include_router(room_router, prefix=IR)

    @test_app.get(f"{STORAGE}/{{bucket}}/{{key:path}}", response_model=None)
    async def _bucket(bucket: str, key: str, response_content_type: str | None = None) -> Response:
        stored = store.objects.get(key)
        if bucket != BUCKET or stored is None:
            raise NotFoundError(f"no object at {key}")
        return Response(content=stored[0], media_type=response_content_type or stored[1])

    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def auth_header(db_session, user) -> dict[str, str]:
    from app.services.auth.issue_tokens import issue_tokens

    access, _refresh = await issue_tokens(db_session, user)
    return {"Authorization": f"Bearer {access}"}


async def a_facilitator(db_session, room_app):
    user = await make_user(db_session)
    role = (
        await db_session.execute(
            select(Role).where(Role.app_id == room_app.id, Role.role_key == "facilitator")
        )
    ).scalar_one()
    await make_user_app_role(db_session, user.id, room_app.id, role.id)
    return user


async def a_raised_hand(db_session, store):
    db_session.add(IRSession(id="sessao-1", pericope="P03"))
    await db_session.commit()
    return await service.raise_question(
        db_session,
        device_id="tablet-1",
        session_id="sessao-1",
        pericope="P03",
        audio=AUDIO,
        store=store,
    )


@pytest.mark.asyncio
async def test_a_facilitator_plays_a_question_and_hears_it(client, db_session, room_app, store):
    """The whole point: the address the queue hands out ends in the recording.

    Starting from the queue rather than from a route the test builds itself is deliberate.
    The two ends drifted apart once already — the queue minted addresses on a route that
    refused them — and only a test that walks from one to the other notices.
    """
    question = await a_raised_hand(db_session, store)
    user = await a_facilitator(db_session, room_app)
    headers = await auth_header(db_session, user)

    listed = await client.get(f"{IR}/facilitator/questions", headers=headers)
    assert listed.status_code == 200, listed.text[:300]
    queued = listed.json()["questions"][0]
    assert queued["question_id"] == question.id

    played = await client.get(queued["audio_url"], headers=headers, follow_redirects=True)

    assert played.status_code == 200, (
        f"o facilitador apertou play no endereco que a propria fila deu "
        f"({queued['audio_url']}) e recebeu {played.status_code}: {played.text[:300]}"
    )
    assert played.content == AUDIO, "chegou ao player outra coisa que nao a gravacao"
    assert played.headers["content-type"] == store.objects[question.audio_key][1], (
        "o navegador foi informado de um tipo que contradiz os bytes guardados, que e um "
        "player quebrado sem nenhuma mensagem de erro"
    )


@pytest.mark.asyncio
async def test_playing_a_question_carries_no_shared_room_key(client, db_session, room_app, store):
    """The credential is the person's, not the tablet's.

    Asserting only that the request succeeded would pass on a route that accepts either
    one, so the absence of the header is what is asserted.
    """
    question = await a_raised_hand(db_session, store)
    user = await a_facilitator(db_session, room_app)
    headers = await auth_header(db_session, user)

    assert not any(name.lower() == "x-room-key" for name in headers)

    played = await client.get(
        f"{IR}/facilitator/questions/{question.id}/audio", headers=headers, follow_redirects=True
    )

    assert played.status_code == 200, played.text[:300]
    assert played.content == AUDIO


@pytest.mark.asyncio
async def test_the_room_key_alone_does_not_open_the_question(client, db_session, room_app, store):
    """The half of Behaviour 2 the absence check cannot reach.

    A route that took either credential would satisfy every assertion above, since those
    only ever describe the request the test chose to send. This one sends the shared key
    on its own: it is the same on every tablet and names no one.
    """
    question = await a_raised_hand(db_session, store)

    played = await client.get(
        f"{IR}/facilitator/questions/{question.id}/audio",
        headers={"X-Room-Key": "sala-local-dev"},
        follow_redirects=False,
    )

    assert played.status_code == 401


@pytest.mark.asyncio
async def test_listening_without_a_login_is_refused(client, db_session, room_app, store):
    question = await a_raised_hand(db_session, store)

    played = await client.get(f"{IR}/facilitator/questions/{question.id}/audio")

    assert played.status_code == 401


@pytest.mark.asyncio
async def test_storage_trouble_is_not_dressed_up_as_a_missing_recording(
    client, db_session, room_app, store, settings, monkeypatch
):
    """A bucket that cannot be reached is not the same news as a hand with no recording.

    Answering 404 for both is the confusion this whole path already cost once: the
    facilitator is standing in front of someone waiting, and 'no such recording' sends
    them looking for the wrong problem.
    """
    question = await a_raised_hand(db_session, store)
    user = await a_facilitator(db_session, room_app)
    monkeypatch.setattr(settings, "gcs_platform_bucket", "", raising=False)

    played = await client.get(
        f"{IR}/facilitator/questions/{question.id}/audio",
        headers=await auth_header(db_session, user),
        follow_redirects=False,
    )

    assert played.status_code >= 400
    assert played.status_code != 404, (
        f"o armazenamento indisponivel foi servido como 'gravacao inexistente' "
        f"({played.status_code})"
    )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "ENG-439 traz o escopo por projeto e esta sendo construida sobre a linha de "
        "aparelhos, a partir da main. IRQuestion nao tem team_id nem project_id nesta "
        "base, e nao ha caminho de um usuario ate um device_id, entao nao existe coluna "
        "por onde recusar. Fica estrito de proposito: quando o escopo da ENG-439 chegar, "
        "este teste passa, a suite fica vermelha e alguem tem de vir aqui remover a marca."
    ),
)
@pytest.mark.asyncio
async def test_a_question_the_facilitator_has_no_link_to_is_refused(
    client, db_session, room_app, store
):
    """Acesso ao app nao e o mesmo que vinculo com o trabalho desta equipe."""
    question = await a_raised_hand(db_session, store)
    stranger = await a_facilitator(db_session, room_app)

    played = await client.get(
        f"{IR}/facilitator/questions/{question.id}/audio",
        headers=await auth_header(db_session, stranger),
        follow_redirects=False,
    )

    assert played.status_code in (403, 404)
