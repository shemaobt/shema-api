"""The address handed out for a question's audio has to answer.

Both halves of the hand travel as a URL: the team is handed one for the facilitator's
spoken reply, the facilitator one for the team's recording. Both used to point at the
room's voice route, which serves this room's synthesized speech and nothing else, so every
one of those addresses was a 404 — the queue could not be listened to and no answer ever
reached the tablet that asked.
"""

from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.internalization_room import questions as service
from app.services.internalization_room.voice_handles import to_handle
from tests.baker import make_user

PREFIX = "/api/internalization-room"
KEY = "sala-de-teste"
DEVICE = "tablet-da-equipe-1"
#: Whose the question is. The inbox reaches a question through the team that owns it, so a
#: hand raised by nobody's tablet reaches nobody — which is the state this file used to be
#: written in, back when a question had no owner to be reached through.
TEAM = "equipe-1"


class MemoryStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def get(self, key: str) -> bytes | None:
        return self.objects.get(key)

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = data


@pytest.fixture()
def store(monkeypatch: pytest.MonkeyPatch) -> MemoryStore:
    memory = MemoryStore()
    monkeypatch.setattr(service, "_store", lambda settings=None: memory)
    return memory


@pytest.fixture()
async def facilitator(db_session: AsyncSession):
    return await make_user(db_session, email="facilitadora@example.com", is_platform_admin=True)


@pytest.fixture()
async def client(db_session: AsyncSession, facilitator: Any, monkeypatch: pytest.MonkeyPatch):
    from fastapi import FastAPI

    from app.api.internalization_room import router
    from app.core.auth_middleware import get_current_user
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    monkeypatch.setattr(get_settings(), "internalization_room_api_key", KEY, raising=False)

    test_app = FastAPI()
    test_app.include_router(router, prefix=PREFIX)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    async def _current_user():
        return facilitator

    test_app.dependency_overrides[get_db] = _get_db
    test_app.dependency_overrides[get_current_user] = _current_user
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _ask(db_session: AsyncSession, store: MemoryStore):
    return await service.raise_question(
        db_session,
        device_id=DEVICE,
        session_id="sessao-1",
        pericope="P03",
        audio=b"a equipe perguntou",
        project_id=TEAM,
        store=store,
    )


async def test_the_team_can_fetch_the_reply_it_was_handed(
    client: httpx.AsyncClient, db_session: AsyncSession, store: MemoryStore
) -> None:
    question = await _ask(db_session, store)
    await service.answer_with_voice(
        db_session, question, audio=b"o facilitador respondeu", answered_by="user-1", store=store
    )

    listed = await client.get(
        f"{PREFIX}/questions/replies",
        headers={"X-Room-Key": KEY, "X-Room-Device": DEVICE},
    )
    assert listed.status_code == 200, listed.text
    url = listed.json()["replies"][0]["audio_url"]

    fetched = await client.get(url, headers={"X-Room-Key": KEY})

    assert fetched.status_code == 200, (
        "the reply address the app is handed has to answer — a 404 here is a team told "
        f"their question was received and then left with silence: {fetched.text[:200]}"
    )
    assert fetched.content == b"o facilitador respondeu"


async def test_the_facilitator_can_hear_what_the_team_asked(
    client: httpx.AsyncClient, db_session: AsyncSession, store: MemoryStore
) -> None:
    await _ask(db_session, store)

    listed = await client.get(f"{PREFIX}/facilitator/questions")
    assert listed.status_code == 200, listed.text
    url = listed.json()["questions"][0]["audio_url"]

    fetched = await client.get(url)

    assert fetched.status_code == 200, (
        "a facilitator holds no device key, so the queue's audio has to open to their "
        f"own credential or the queue cannot be worked at all: {fetched.text[:200]}"
    )
    assert fetched.content == b"a equipe perguntou"


@pytest.mark.parametrize(
    "key",
    [
        "tts/RoomVoice/eleven_turbo_v2_5/mp3_44100_128/abc/def.mp3",
        "recordings/alguem/privado.m4a",
        "internalization-room/questions/../../etc/passwd",
    ],
)
async def test_a_handle_for_something_else_is_refused(
    client: httpx.AsyncClient, store: MemoryStore, key: str
) -> None:
    """A handle is a client-supplied instruction about which object to read."""
    store.objects[key] = b"nao e desta rota"

    fetched = await client.get(
        f"{PREFIX}/questions/audio/{to_handle(key)}", headers={"X-Room-Key": KEY}
    )

    assert fetched.status_code == 404, fetched.text
