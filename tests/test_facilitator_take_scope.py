"""ENG-534 — the same hole, in the two routes that serve what a team recorded.

These were not in the issue when it was written. The contract measurement that found the
question routes was scoped to questions, so the take routes kept the same shape nobody had
looked at: `FacilitatorUser`, then the resource by id, and no question of whose it is.

A take is not a lesser thing to leak than a question. It is the whole team telling the
passage aloud — the recording the session exists to produce — and `listen_to_take` hands
back a signed URL that outlives the request, so a leak here is a leak of the bytes, not of
a row.

Both refusals match the "no such thing" the routes already answer, for the reason the
question file states.
"""

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ProjectRole
from app.db.models.internalization_room import IRSession, IRTake, IRTakeKind
from tests.baker import (
    grant_facilitator_app_role,
    make_language,
    make_project,
    make_project_user_access,
    make_user,
)

IR = "/api/internalization-room"


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    from fastapi import FastAPI

    from app.api.internalization_room import router
    from app.api.internalization_room import takes as routes
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    async def _signed(take, **kw) -> str:
        return f"https://storage.example/{take.storage_key}"

    # Patched on the API module, not on the service: `takes.py` imports the name directly,
    # so rebinding it on the service leaves the route holding the original.
    monkeypatch.setattr(routes, "listen_url", _signed)

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
    user = await make_user(db, email=email)
    language = await make_language(db, name=f"Lang {email}", code=email[:3])
    project = await make_project(db, language.id, name=f"Team {email}")
    await make_project_user_access(db, project.id, user.id, role=ProjectRole.FACILITATOR)
    await grant_facilitator_app_role(db, user.id)

    from app.services.auth.issue_tokens import issue_tokens

    access, _refresh = await issue_tokens(db, user)
    return project, {"Authorization": f"Bearer {access}"}


async def a_recorded_session(db: AsyncSession, project_id: str | None, *, tag: str):
    """A session with one take in it. Returns (session, take)."""
    session = IRSession(id=f"sessao-{tag}", pericope="P03", project_id=project_id)
    db.add(session)
    await db.flush()

    take = IRTake(
        id=f"take-{tag}",
        session_id=session.id,
        device_id=f"tablet-{tag}",
        project_id=project_id,
        pericope="P03",
        kind=IRTakeKind.ENSAIO,
        scope="passagem-inteira",
        storage_key=f"internalization-room/takes/{tag}.m4a",
        size_bytes=1024,
        sha256="0" * 64,
        crc32c="AAAAAA==",
        content_type="audio/mp4",
    )
    db.add(take)
    await db.commit()
    return session, take


def _shape(body: dict, *ids: str) -> dict:
    """The refusal with the caller's own ids blanked. See the question-scope file."""
    blanked = dict(body)
    for value in ids:
        blanked = {
            k: (v.replace(value, "<id>") if isinstance(v, str) else v) for k, v in blanked.items()
        }
    return blanked


def takes_url(session_id: str) -> str:
    return f"{IR}/facilitator/sessions/{session_id}/takes"


def take_audio_url(take_id: str) -> str:
    return f"{IR}/facilitator/takes/{take_id}/audio"


# Behaviour 1 — another team's session and take are refused.


async def test_listing_another_teams_takes_is_refused(client, db_session):
    _mine, headers = await a_facilitator(db_session, email="a@example.com")
    theirs, _ = await a_facilitator(db_session, email="b@example.com")
    session, _take = await a_recorded_session(db_session, theirs.id, tag="deles")

    refused = await client.get(takes_url(session.id), headers=headers)

    assert refused.status_code == 404


async def test_listening_to_another_teams_take_is_refused(client, db_session):
    _mine, headers = await a_facilitator(db_session, email="a@example.com")
    theirs, _ = await a_facilitator(db_session, email="b@example.com")
    _session, take = await a_recorded_session(db_session, theirs.id, tag="deles")

    refused = await client.get(take_audio_url(take.id), headers=headers)

    assert refused.status_code == 404


# Behaviour 2 — indistinguishable from a session or take that never existed.


async def test_the_refusal_matches_the_one_for_a_session_that_does_not_exist(client, db_session):
    _mine, headers = await a_facilitator(db_session, email="a@example.com")
    theirs, _ = await a_facilitator(db_session, email="b@example.com")
    session, take = await a_recorded_session(db_session, theirs.id, tag="deles")

    absent_session, absent_take = "sessao-que-nunca-existiu", "take-que-nunca-existiu"

    not_yours = await client.get(takes_url(session.id), headers=headers)
    no_such = await client.get(takes_url(absent_session), headers=headers)

    assert not_yours.status_code == no_such.status_code
    assert _shape(not_yours.json(), session.id) == _shape(no_such.json(), absent_session)

    not_yours_take = await client.get(take_audio_url(take.id), headers=headers)
    no_such_take = await client.get(take_audio_url(absent_take), headers=headers)

    assert not_yours_take.status_code == no_such_take.status_code
    assert _shape(not_yours_take.json(), take.id) == _shape(no_such_take.json(), absent_take)


# Behaviour 3 — the happy path is untouched.


async def test_a_facilitator_still_lists_and_plays_their_own_teams_takes(client, db_session):
    mine, headers = await a_facilitator(db_session, email="a@example.com")
    session, take = await a_recorded_session(db_session, mine.id, tag="minha")

    listed = await client.get(takes_url(session.id), headers=headers)
    played = await client.get(take_audio_url(take.id), headers=headers, follow_redirects=False)

    assert listed.status_code == 200
    assert [row["take_id"] for row in listed.json()["takes"]] == [take.id]
    assert played.status_code == 307


# Behaviour 4 — a session that names no team belongs to nobody.


async def test_a_session_with_no_team_is_refused_rather_than_open_to_everyone(client, db_session):
    """The pre-ENG-440 shape, and today's common one."""
    _mine, headers = await a_facilitator(db_session, email="a@example.com")
    session, take = await a_recorded_session(db_session, None, tag="sem-equipe")

    assert (await client.get(takes_url(session.id), headers=headers)).status_code == 404
    assert (await client.get(take_audio_url(take.id), headers=headers)).status_code == 404
