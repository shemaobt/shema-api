"""Whether the team can hear the telling it just recorded.

The room records the back translation and the recording leaves for the bucket. Until now
the only route that hands out playable audio asked for a facilitator's login, and the team
never signs in — so the tablet uploaded the telling and lost it. The "Onde Mora o Erro"
screen puts two play buttons side by side and the second one had nothing behind it.

What the room presents is a key that is the same on every tablet. That is why the route
here takes a session *and* a take, and refuses a take that belongs to another session: a
shared credential that accepted a bare identifier would be a key to the whole archive.
"""

from __future__ import annotations

import base64

import httpx
import pytest
from google_crc32c import Checksum
from httpx import ASGITransport
from sqlalchemy import select

from app.core.enums import ProjectRole
from app.db.models.auth import Role
from app.db.models.internalization_room import IRSession, IRTakeKind
from app.services.internalization_room import takes as service
from app.services.platform.storage import StoredObject
from tests.baker import (
    make_app,
    make_language,
    make_project,
    make_project_user_access,
    make_role,
    make_user,
    make_user_app_role,
)

APP_KEY = "internalization-room"
IR = "/api/internalization-room"
ROOM_KEY = "chave-da-sala"
BUCKET = "balde-de-teste"
STORAGE = "https://armazenamento.exemplo"
AUDIO = b"a equipe contou de volta em portugues"


class MemoryStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def get(self, key: str) -> bytes | None:
        return self.objects.get(key)

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = data

    async def stat(self, key: str) -> StoredObject | None:
        stored = self.objects.get(key)
        if stored is None:
            return None
        checksum = Checksum()
        checksum.update(stored)
        return StoredObject(
            size=len(stored), crc32c=base64.b64encode(checksum.digest()).decode("ascii")
        )


@pytest.fixture()
async def room_app(db_session):
    app = await make_app(db_session, app_key=APP_KEY, name="Internalization Room")
    await make_role(db_session, app.id, role_key="facilitator", label="Facilitator", is_system=True)
    return app


@pytest.fixture(autouse=True)
def storage_that_signs_without_google(monkeypatch):
    """The bucket's signature is the one thing a test cannot ask Google for.

    Everything else on the path runs for real, including the check that a bucket is
    configured at all and the content type the address is minted for.
    """
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "gcs_platform_bucket", BUCKET, raising=False)
    monkeypatch.setattr(get_settings(), "internalization_room_api_key", ROOM_KEY, raising=False)

    async def _signed(bucket: str, key: str, **_kwargs: object) -> str:
        return f"{STORAGE}/{bucket}/{key}?assinado"

    monkeypatch.setattr(service, "generate_signed_download_url", _signed)


@pytest.fixture()
async def client(db_session):
    from fastapi import FastAPI

    from app.api.internalization_room import router as room_router
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    test_app = FastAPI()
    test_app.include_router(room_router, prefix=IR)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def a_session_that_recorded(db_session, session_id: str, project_id: str | None = None):
    session = IRSession(id=session_id, pericope="P03", project_id=project_id)
    db_session.add(session)
    await db_session.commit()
    take = await service.store_take(
        db_session,
        session_id=session.id,
        device_id=f"tablet-{session_id}",
        project_id=project_id,
        pericope=session.pericope,
        kind=IRTakeKind.RETRO,
        scope=session.pericope,
        audio=AUDIO + session_id.encode(),
        pass_number=1,
        chunk_index=1,
        store=MemoryStore(),
    )
    return session, take


async def auth_header(db_session, user) -> dict[str, str]:
    from app.services.auth.issue_tokens import issue_tokens

    access, _refresh = await issue_tokens(db_session, user)
    return {"Authorization": f"Bearer {access}"}


async def a_facilitator_of(db_session, room_app, project):
    user = await make_user(db_session)
    await make_project_user_access(db_session, project.id, user.id, role=ProjectRole.FACILITATOR)
    role = (
        await db_session.execute(
            select(Role).where(Role.app_id == room_app.id, Role.role_key == "facilitator")
        )
    ).scalar_one()
    await make_user_app_role(db_session, user.id, room_app.id, role.id)
    return user


async def a_team(db_session, *, code: str, name: str):
    language = await make_language(db_session, name=f"Lingua {code}", code=code)
    return await make_project(db_session, language.id, name=name)


@pytest.mark.asyncio
async def test_the_room_hears_a_take_of_its_own_session(client, db_session):
    session, take = await a_session_that_recorded(db_session, "sessao-da-equipe")

    response = await client.get(
        f"{IR}/sessions/{session.id}/takes/{take.id}/audio",
        headers={"X-Room-Key": ROOM_KEY},
        follow_redirects=False,
    )

    assert response.status_code == 307, response.text[:300]
    assert take.storage_key in response.headers["location"]
    assert response.headers["location"].startswith(STORAGE)
    assert response.content == b"", "a API não carrega os bytes de uma tomada inteira"


@pytest.mark.asyncio
async def test_the_room_does_not_hear_the_take_of_another_session(client, db_session):
    """The case the shared key makes necessary.

    Every tablet in the field presents the same string, so a take named on its own would
    be reachable by anyone holding the app — this is what keeps the key from being a key
    to the whole archive.

    The same call with the session's own take is asked first and is not decoration: a
    refusal on its own is what an address that leads nowhere also answers, and this case
    has to mean the door was open and this one take did not come through it.
    """
    mine, my_take = await a_session_that_recorded(db_session, "sessao-desta-equipe")
    _theirs, their_take = await a_session_that_recorded(db_session, "sessao-de-outra-equipe")

    opened = await client.get(
        f"{IR}/sessions/{mine.id}/takes/{my_take.id}/audio",
        headers={"X-Room-Key": ROOM_KEY},
        follow_redirects=False,
    )
    response = await client.get(
        f"{IR}/sessions/{mine.id}/takes/{their_take.id}/audio",
        headers={"X-Room-Key": ROOM_KEY},
        follow_redirects=False,
    )

    assert opened.status_code == 307, opened.text[:300]
    assert response.status_code == 404
    assert "location" not in response.headers


@pytest.mark.asyncio
async def test_without_the_room_credential_nothing_plays(client, db_session):
    session, take = await a_session_that_recorded(db_session, "sessao-sem-chave")

    response = await client.get(
        f"{IR}/sessions/{session.id}/takes/{take.id}/audio", follow_redirects=False
    )

    assert response.status_code == 401
    assert "location" not in response.headers


@pytest.mark.asyncio
async def test_an_absent_take_and_somebody_elses_answer_alike(client, db_session):
    """So the refusal cannot be read as an inventory of what exists.

    Only the identifier the caller itself sent may differ between the two answers; with
    that put back, the bodies have to be the same string.

    The reachable take is asked for first for the reason the case above gives: two
    identical refusals are also what an address that leads nowhere gives twice.
    """
    mine, my_take = await a_session_that_recorded(db_session, "sessao-que-pergunta")
    _theirs, their_take = await a_session_that_recorded(db_session, "sessao-que-nao-e-dela")
    absent = "tomada-que-nunca-existiu"

    opened = await client.get(
        f"{IR}/sessions/{mine.id}/takes/{my_take.id}/audio",
        headers={"X-Room-Key": ROOM_KEY},
        follow_redirects=False,
    )
    elsewhere = await client.get(
        f"{IR}/sessions/{mine.id}/takes/{their_take.id}/audio",
        headers={"X-Room-Key": ROOM_KEY},
        follow_redirects=False,
    )
    nowhere = await client.get(
        f"{IR}/sessions/{mine.id}/takes/{absent}/audio",
        headers={"X-Room-Key": ROOM_KEY},
        follow_redirects=False,
    )

    assert opened.status_code == 307, opened.text[:300]
    assert elsewhere.status_code == nowhere.status_code == 404
    assert elsewhere.text.replace(their_take.id, absent) == nowhere.text


@pytest.mark.asyncio
async def test_the_facilitator_door_is_where_it_was(client, db_session, room_app):
    """The regression of the slice: opening one door must not move the other.

    A facilitator still plays a take of their own team by signing in, and the shared room
    key still gets nothing on that route — which is the whole reason a second route had
    to be written instead of widening this one.
    """
    project = await a_team(db_session, code="tkf", name="Equipe do facilitador")
    _session, take = await a_session_that_recorded(db_session, "sessao-do-facilitador", project.id)
    user = await a_facilitator_of(db_session, room_app, project)

    played = await client.get(
        f"{IR}/facilitator/takes/{take.id}/audio",
        headers=await auth_header(db_session, user),
        follow_redirects=False,
    )
    with_the_room_key = await client.get(
        f"{IR}/facilitator/takes/{take.id}/audio",
        headers={"X-Room-Key": ROOM_KEY},
        follow_redirects=False,
    )

    assert played.status_code == 307, played.text[:300]
    assert take.storage_key in played.headers["location"]
    assert with_the_room_key.status_code == 401
