"""ENG-533 — the facilitator's play button, and what has to arrive at the end of it.

`listen_to_question` answered `307` to a short-lived signed URL, which is the right shape
for serving audio and the wrong shape for the only thing that consumes it. The Desk draws
`<audio src={audioUrl}>`, and **a media element sends no headers**: it hit the route, got
`401` before the redirect ever happened, and no facilitator has ever heard a question.

So the address travels in the body, to a caller who *can* send `Authorization`, and the
media element is pointed at the signed URL instead of at us. Of the four paths measured in
chromium, firefox and webkit, this is the one that needs no CORS at all: media elements
fetch in `no-cors` mode, and after a cross-origin redirect the `Origin` becomes `null` —
which in a bucket's CORS list is not an origin but a wildcard for any redirected or
sandboxed context.

## The bytes rule, which is why storage is an HTTP endpoint here

ENG-434 paid for this: its test asserted on the URL's **prefix** and never made the
request, so a P0 survived a green suite. The rule that came out of it is not "follow the
redirect" — it is **do not assert on the address, assert on what arrives**. That the
address now comes from a body rather than from a `Location` changes nothing: these cases
read the URL, request it, and assert on the bytes and on the declared type that come back.

Storage is stubbed as an endpoint rather than as a return value precisely so the request
can be made. The stub honours `response-content-type` because the bucket honours it, and
that parameter is how the browser learns what it is about to play.

## What is not asserted here, and why

**That an expired URL is refused.** The refusal belongs to the storage provider, not to
this codebase: proving it needs either the network or a local reimplementation of V4
verification for the test to assert against — which is asserting on the double. What is
ours is the window we ask for and the instant we promise the caller, and both are below.
"""

from datetime import UTC, datetime
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ProjectRole
from app.db.models.internalization_room import IRQuestion, IRQuestionStatus, IRSession
from app.services.internalization_room import questions as service
from tests.baker import (
    grant_facilitator_app_role,
    make_language,
    make_project,
    make_project_user_access,
    make_user,
)

IR = "/api/internalization-room"
STORAGE = "/armazenamento"
BUCKET = "balde-de-teste"
SPOKEN = b"a pergunta que a equipe gravou, em bytes"
MIME = "audio/mp4"


@pytest.fixture()
def store() -> dict[str, tuple[bytes, str]]:
    return {}


@pytest.fixture()
async def client(db_session: AsyncSession, store, monkeypatch: pytest.MonkeyPatch):
    """The room's routes, plus an endpoint standing in for signed storage.

    The stub is an HTTP endpoint rather than a return value so that the address the API
    hands out can actually be requested. Without that, every case here would be asserting
    on a string.
    """
    from fastapi import FastAPI, Response

    from app.api.internalization_room import router
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import NotFoundError, register_exception_handlers

    monkeypatch.setattr(get_settings(), "gcs_platform_bucket", BUCKET, raising=False)

    async def _signed(
        bucket: str,
        key: str,
        *,
        expiry_minutes: int,
        response_content_type: str | None = None,
    ) -> str:
        query = f"?response-content-type={response_content_type}" if response_content_type else ""
        return f"http://test{STORAGE}/{bucket}/{key}{query}&X-Goog-Expires={expiry_minutes * 60}"

    monkeypatch.setattr(service, "generate_signed_download_url", _signed)

    test_app = FastAPI()
    test_app.include_router(router, prefix=IR)

    @test_app.get(f"{STORAGE}/{{bucket}}/{{key:path}}", response_model=None)
    async def _bucket(bucket: str, key: str, response_content_type: str | None = None) -> Response:
        stored = store.get(key)
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


async def a_facilitator(db: AsyncSession, *, email: str = "fac@example.com"):
    user = await make_user(db, email=email)
    language = await make_language(db, name=f"Lang {email}", code=email[:3])
    project = await make_project(db, language.id, name=f"Team {email}")
    await make_project_user_access(db, project.id, user.id, role=ProjectRole.FACILITATOR)
    await grant_facilitator_app_role(db, user.id)

    from app.services.auth.issue_tokens import issue_tokens

    access, _refresh = await issue_tokens(db, user)
    return project, {"Authorization": f"Bearer {access}"}


async def a_recorded_question(db: AsyncSession, store, project_id: str, *, tag: str) -> IRQuestion:
    """A raised hand whose audio is really in the stubbed bucket."""
    key = f"internalization-room/questions/{tag}.m4a"
    store[key] = (SPOKEN, MIME)

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


def audio_url(question_id: str) -> str:
    return f"{IR}/facilitator/questions/{question_id}/audio"


# Behaviour 1 — the address comes back in the body, and what is at the end of it is the audio.


async def test_the_route_answers_with_an_address_the_facilitator_can_hand_to_a_media_element(
    client, db_session, store
):
    project, headers = await a_facilitator(db_session)
    question = await a_recorded_question(db_session, store, project.id, tag="ouvida")

    answered = await client.get(audio_url(question.id), headers=headers)

    assert answered.status_code == 200, answered.text
    assert answered.json()["url"].startswith("http")


async def test_what_arrives_at_that_address_is_the_recording_and_it_says_what_it_is(
    client, db_session, store
):
    """The bytes rule from ENG-434, on the new shape.

    The address is requested with **no** `Authorization`, because that is the whole point:
    a media element cannot send one. What is asserted is the payload and the declared
    type, never the string that led here.
    """
    project, headers = await a_facilitator(db_session)
    question = await a_recorded_question(db_session, store, project.id, tag="ouvida")

    address = (await client.get(audio_url(question.id), headers=headers)).json()["url"]
    played = await client.get(address)

    assert played.status_code == 200, played.text[:200]
    assert played.content == SPOKEN
    assert played.headers["content-type"].startswith(MIME)


async def test_the_address_needs_no_authorization_of_its_own(client, db_session, store):
    """Asserted separately because it is the property the Desk depends on.

    The case above happens not to send a header; this one says that not sending it is the
    contract. An address that only worked for a caller holding a Bearer would put us back
    where ENG-533 started.
    """
    project, headers = await a_facilitator(db_session)
    question = await a_recorded_question(db_session, store, project.id, tag="sem-cabecalho")

    address = (await client.get(audio_url(question.id), headers=headers)).json()["url"]
    played = await client.get(address, headers={})

    assert played.status_code == 200
    assert played.content == SPOKEN


# Behaviour 2 — the window is short, and the caller is told when it closes.


async def test_the_address_carries_the_short_window_it_was_signed_for(client, db_session, store):
    project, headers = await a_facilitator(db_session)
    question = await a_recorded_question(db_session, store, project.id, tag="janela")

    address = (await client.get(audio_url(question.id), headers=headers)).json()["url"]

    seconds = int(parse_qs(urlparse(address).query)["X-Goog-Expires"][0])
    assert seconds == service.LISTEN_MINUTES * 60


async def test_the_window_is_short_enough_that_widening_it_breaks_this_case(client):
    """A ceiling, so nobody raises the constant to hours without this saying so.

    The number is not sacred; the order of magnitude is. A signed address is a bearer
    credential for one object, and its worth to whoever finds it is measured in how long
    it keeps working.
    """
    assert service.LISTEN_MINUTES <= 15


async def test_the_body_says_when_the_address_stops_working(client, db_session, store):
    """So the Desk can fetch a fresh one instead of discovering it with a silent play.

    Without this the only way to learn the address died is to point a media element at it
    and watch nothing happen — which, on a screen whose whole job is playing a recording,
    is indistinguishable from a recording that was never there.
    """
    project, headers = await a_facilitator(db_session)
    question = await a_recorded_question(db_session, store, project.id, tag="prazo")

    answered = (await client.get(audio_url(question.id), headers=headers)).json()

    expires_at = datetime.fromisoformat(answered["expires_at"])
    assert expires_at.tzinfo is not None, "um instante sem fuso nao diz quando nada acontece"
    window = (expires_at - datetime.now(UTC)).total_seconds()
    assert 0 < window <= service.LISTEN_MINUTES * 60


async def test_the_promised_instant_matches_the_window_the_address_was_signed_for(
    client, db_session, store
):
    """The two halves have to agree, or the promise is decoration.

    A body that says fifteen minutes over an address signed for one is worse than saying
    nothing: the Desk would keep a dead address believing it good.
    """
    project, headers = await a_facilitator(db_session)
    question = await a_recorded_question(db_session, store, project.id, tag="coerencia")

    answered = (await client.get(audio_url(question.id), headers=headers)).json()

    signed_for = int(parse_qs(urlparse(answered["url"]).query)["X-Goog-Expires"][0])
    promised = (datetime.fromisoformat(answered["expires_at"]) - datetime.now(UTC)).total_seconds()
    assert abs(promised - signed_for) < 5


# Behaviour 3 — a recording that is not there is not dressed up as one that is.


async def test_a_question_with_no_recording_is_refused(client, db_session, store):
    """The empty string, not NULL: `audio_key` is a non-nullable column, so a hand with
    nothing behind it is one whose key is blank."""
    project, headers = await a_facilitator(db_session)
    question = await a_recorded_question(db_session, store, project.id, tag="muda")
    question.audio_key = ""
    await db_session.commit()

    refused = await client.get(audio_url(question.id), headers=headers)

    assert refused.status_code == 404
