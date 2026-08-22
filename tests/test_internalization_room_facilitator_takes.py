"""Who can listen to what the team recorded.

The room has two audiences that never share a route. The team's app carries a shared device
key and never signs in; a facilitator is a person, signs in, and comes through the platform's
own app access. Playback belongs to the second one — the tablet already holds its own copy,
and the room key is the same on every tablet.
"""

from __future__ import annotations

import base64

import httpx
import pytest
from google_crc32c import Checksum
from httpx import ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import Role
from app.db.models.internalization_room import IRSession, IRTakeKind
from app.services.internalization_room import takes as service
from app.services.platform.storage import StoredObject
from tests.baker import make_app, make_role, make_user, make_user_app_role

APP_KEY = "internalization-room"
IR = "/api/internalization-room"
AUDIO = b"a equipe contou a passagem inteira"


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


async def auth_header(db_session, user) -> dict[str, str]:
    from app.services.auth.issue_tokens import issue_tokens

    access, _refresh = await issue_tokens(db_session, user)
    return {"Authorization": f"Bearer {access}"}


async def grant_role(db_session, app_id: str, user_id: str, role_key: str) -> None:
    role = (
        await db_session.execute(
            select(Role).where(Role.app_id == app_id, Role.role_key == role_key)
        )
    ).scalar_one()
    await make_user_app_role(db_session, user_id, app_id, role.id)


async def _session_with_a_take(db_session):
    session = IRSession(id="sessao-1", pericope="P03")
    db_session.add(session)
    await db_session.commit()
    take = await service.store_take(
        db_session,
        session_id=session.id,
        device_id="tablet-1",
        pericope=session.pericope,
        kind=IRTakeKind.ENSAIO,
        scope="passagem-inteira",
        audio=AUDIO,
        store=MemoryStore(),
    )
    return session, take


@pytest.mark.asyncio
async def test_a_facilitator_sees_what_a_session_recorded(client, db_session, room_app):
    session, take = await _session_with_a_take(db_session)
    user = await make_user(db_session)
    await grant_role(db_session, room_app.id, user.id, "facilitator")

    response = await client.get(
        f"{IR}/facilitator/sessions/{session.id}/takes",
        headers=await auth_header(db_session, user),
    )

    assert response.status_code == 200
    body = response.json()
    assert [t["take_id"] for t in body["takes"]] == [take.id]
    assert body["takes"][0]["verified"] is True


@pytest.mark.asyncio
async def test_without_a_login_nobody_listens(client, db_session, room_app):
    session, _take = await _session_with_a_take(db_session)

    response = await client.get(f"{IR}/facilitator/sessions/{session.id}/takes")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_the_room_key_does_not_open_the_facilitator_door(client, db_session, room_app):
    session, _take = await _session_with_a_take(db_session)

    response = await client.get(
        f"{IR}/facilitator/sessions/{session.id}/takes",
        headers={"X-Room-Key": "sala-local-dev"},
    )

    assert response.status_code == 401, (
        "a chave é a mesma em todos os tablets — ela identifica o app, não uma pessoa"
    )


@pytest.mark.asyncio
async def test_a_signed_in_user_without_the_app_is_refused(client, db_session, room_app):
    session, _take = await _session_with_a_take(db_session)
    stranger = await make_user(db_session)

    response = await client.get(
        f"{IR}/facilitator/sessions/{session.id}/takes",
        headers=await auth_header(db_session, stranger),
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_listening_redirects_to_storage_instead_of_proxying(
    client, db_session, room_app, monkeypatch
):
    _session, take = await _session_with_a_take(db_session)
    user = await make_user(db_session)
    await grant_role(db_session, room_app.id, user.id, "facilitator")
    from app.api.internalization_room import takes as route

    monkeypatch.setattr(route, "listen_url", lambda take: _signed(take.storage_key))

    response = await client.get(
        f"{IR}/facilitator/takes/{take.id}/audio",
        headers=await auth_header(db_session, user),
        follow_redirects=False,
    )

    assert response.status_code == 307
    assert take.storage_key in response.headers["location"]
    assert response.content == b"", "a API não carrega os bytes de uma tomada inteira"


async def _signed(key: str) -> str:
    return f"https://storage.example/{key}?assinado"


@pytest.mark.asyncio
async def test_listening_without_a_login_is_refused(client, db_session, room_app):
    _session, take = await _session_with_a_take(db_session)

    response = await client.get(f"{IR}/facilitator/takes/{take.id}/audio")

    assert response.status_code == 401


async def test_a_reviewer_can_tell_the_stretches_apart(db_session: AsyncSession) -> None:
    """N indistinguishable `retro` rows is not a back translation anyone can read.

    `chunk_index` and `pass_number` are stored and were not exposed, so the reviewer could
    not tell stretch three from stretch seven, nor a first telling from its correction.
    """
    store = MemoryStore()
    for index, (chunk, passe) in enumerate([(2, 2), (1, 1), (2, 1)]):
        await service.store_take(
            db_session,
            session_id="s1",
            device_id="tablet-da-equipe-1",
            pericope="P01",
            kind=IRTakeKind.RETRO,
            scope="P01",
            audio=f"trecho {index}".encode(),
            pass_number=passe,
            chunk_index=chunk,
            store=store,
        )

    rows = await service.takes_of(db_session, "s1")
    seen = [(take.chunk_index, take.pass_number) for take in rows]

    assert seen == [(1, 1), (2, 1), (2, 2)], (
        "e a ordem tem de ser a da leitura, não a da chegada: uma retentativa cai depois "
        "de um trecho posterior"
    )
