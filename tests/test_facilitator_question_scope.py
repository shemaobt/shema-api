"""ENG-534 — a facilitator reaches the questions of their own teams and no others.

ENG-452 closed the inbox: the list only ever shows a caller's own teams. The three routes
that *act* on a question were written before "the teams of this facilitator" existed as an
idea, and they ask only for the role. Holding the role is not owning the question, so an
authenticated facilitator with a question id belonging to somebody else's team replies to
that team by voice, closes their card, and listens to their recording.

The refusal is deliberately the same one a question that does not exist gets. A caller who
can tell "not yours" from "no such thing" can map the installation by asking for ids, which
is the rule ENG-443 fixed at the claim and `teams.py` repeats. That is why the cases below
assert the **body** and not only the status: once the status is handled, the message is
where this kind of thing leaks out next.

A question carrying no `project_id` — a row from before ENG-440 — belongs to no team at all,
so nobody facilitates it and everybody is refused. It is not "unowned, therefore open".
"""

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
AUDIO = b"a resposta falada do facilitador"


class MemoryStore:
    """The bucket seam, in memory. The routes under test write and sign, never proxy."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def get(self, key: str) -> bytes | None:
        return self.objects.get(key)

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = data


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    from fastapi import FastAPI

    from app.api.internalization_room import router
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    store = MemoryStore()
    monkeypatch.setattr(service, "_store", lambda *a, **kw: store)

    async def _signed(key: str) -> str:
        return f"https://storage.example/{key}"

    monkeypatch.setattr(service, "listen_url", _signed)

    test_app = FastAPI()
    test_app.include_router(router, prefix=IR)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def a_facilitator(db: AsyncSession, *, email: str):
    """A facilitator with the app role and one team of their own."""
    user = await make_user(db, email=email)
    language = await make_language(db, name=f"Lang {email}", code=email[:3])
    project = await make_project(db, language.id, name=f"Team {email}")
    await make_project_user_access(db, project.id, user.id, role=ProjectRole.FACILITATOR)
    await grant_facilitator_app_role(db, user.id)

    from app.services.auth.issue_tokens import issue_tokens

    access, _refresh = await issue_tokens(db, user)
    return project, {"Authorization": f"Bearer {access}"}


async def a_question_of(db: AsyncSession, project_id: str | None, *, tag: str) -> IRQuestion:
    """A raised hand belonging to ``project_id``, with audio already stored."""
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
        audio_key=f"internalization-room/questions/{tag}.m4a",
    )
    db.add(question)
    await db.commit()
    return question


def audio_url(question_id: str) -> str:
    return f"{IR}/facilitator/questions/{question_id}/audio"


def reply_url(question_id: str) -> str:
    return f"{IR}/facilitator/questions/{question_id}/reply"


def resolve_url(question_id: str) -> str:
    return f"{IR}/facilitator/questions/{question_id}/resolve"


REPLY_FILE = {"files": {"file": ("resposta.m4a", AUDIO, "audio/mp4")}}


# Behaviour 1 — the three routes refuse another team's question.


async def test_listening_to_another_teams_question_is_refused(client, db_session):
    _mine, headers = await a_facilitator(db_session, email="a@example.com")
    theirs, _ = await a_facilitator(db_session, email="b@example.com")
    question = await a_question_of(db_session, theirs.id, tag="deles")

    refused = await client.get(audio_url(question.id), headers=headers)

    assert refused.status_code == 404


async def test_replying_to_another_teams_question_is_refused(client, db_session):
    """And the reply must not land: a refusal that still wrote is not a refusal.

    Asserting the status alone would pass against a route that answers 404 after having
    already recorded the answer against the other team's card.
    """
    _mine, headers = await a_facilitator(db_session, email="a@example.com")
    theirs, _ = await a_facilitator(db_session, email="b@example.com")
    question = await a_question_of(db_session, theirs.id, tag="deles")

    refused = await client.post(reply_url(question.id), headers=headers, **REPLY_FILE)

    assert refused.status_code == 404
    await db_session.refresh(question)
    assert question.status is IRQuestionStatus.OPEN
    assert question.reply_audio_key is None


async def test_resolving_another_teams_question_is_refused(client, db_session):
    _mine, headers = await a_facilitator(db_session, email="a@example.com")
    theirs, _ = await a_facilitator(db_session, email="b@example.com")
    question = await a_question_of(db_session, theirs.id, tag="deles")

    refused = await client.post(resolve_url(question.id), headers=headers)

    assert refused.status_code == 404
    await db_session.refresh(question)
    assert question.status is IRQuestionStatus.OPEN


# Behaviour 2 — the refusal says nothing about whether the question exists.


def _shape(body: dict, *ids: str) -> dict:
    """The refusal with the caller's own ids blanked out.

    The message names the id that was asked for, and comparing bodies literally would
    therefore always differ — on the id the caller themselves sent, which tells them
    nothing they did not already know. What must not differ is everything else: a
    "belongs to another team" hiding behind an equal status is exactly what this looks for.
    """
    blanked = dict(body)
    for value in ids:
        blanked = {
            k: (v.replace(value, "<id>") if isinstance(v, str) else v) for k, v in blanked.items()
        }
    return blanked


async def test_a_question_of_another_team_is_refused_exactly_like_one_that_does_not_exist(
    client, db_session
):
    """Same status and same shape of message, on all three routes.

    A caller who can tell the two apart enumerates ids and learns which questions exist,
    and a question that exists is a team that exists. The status was the easy half; the
    message is the half that gets forgotten.
    """
    _mine, headers = await a_facilitator(db_session, email="a@example.com")
    theirs, _ = await a_facilitator(db_session, email="b@example.com")
    question = await a_question_of(db_session, theirs.id, tag="deles")
    absent = "pergunta-que-nunca-existiu"

    cases = [
        ("GET", audio_url, {}),
        ("POST", resolve_url, {}),
        ("POST", reply_url, REPLY_FILE),
    ]
    for method, url, extra in cases:
        not_yours = await client.request(method, url(question.id), headers=headers, **extra)
        no_such = await client.request(method, url(absent), headers=headers, **extra)

        assert not_yours.status_code == no_such.status_code, f"{method} {url('<id>')}"
        assert _shape(not_yours.json(), question.id) == _shape(no_such.json(), absent), (
            f"a recusa em {method} {url('<id>')} se distingue de 'nao existe' pelo corpo"
        )


# Behaviour 3 — the happy path is untouched.


async def test_a_facilitator_still_reaches_their_own_teams_question(client, db_session):
    """The case that keeps this slice from being "refuse everything".

    Without it, a scope check that answered 404 for everyone would satisfy every other
    case in this file.
    """
    mine, headers = await a_facilitator(db_session, email="a@example.com")
    question = await a_question_of(db_session, mine.id, tag="minha")

    heard = await client.get(audio_url(question.id), headers=headers, follow_redirects=False)
    answered = await client.post(reply_url(question.id), headers=headers, **REPLY_FILE)

    assert heard.status_code == 307
    assert answered.status_code == 200
    await db_session.refresh(question)
    assert question.status is IRQuestionStatus.ANSWERED


async def test_a_facilitator_still_resolves_their_own_teams_question(client, db_session):
    mine, headers = await a_facilitator(db_session, email="a@example.com")
    question = await a_question_of(db_session, mine.id, tag="minha")

    resolved = await client.post(resolve_url(question.id), headers=headers)

    assert resolved.status_code == 200
    await db_session.refresh(question)
    assert question.status is IRQuestionStatus.RESOLVED


# Behaviour 4 — a question that names no team belongs to nobody.


async def test_a_question_with_no_team_is_refused_rather_than_open_to_everyone(client, db_session):
    """A row from before ENG-440. Unowned is not unguarded.

    This is the common shape today, because the room's app does not send its device
    credential yet — so a scope check that treated a null `project_id` as "no restriction"
    would leave most of the table reachable by any facilitator.
    """
    _mine, headers = await a_facilitator(db_session, email="a@example.com")
    orphan = await a_question_of(db_session, None, tag="sem-equipe")

    refused = await client.post(resolve_url(orphan.id), headers=headers)

    assert refused.status_code == 404
    await db_session.refresh(orphan)
    assert orphan.status is IRQuestionStatus.OPEN
