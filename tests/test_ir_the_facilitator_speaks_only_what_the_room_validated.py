"""No request can put words in the facilitator's mouth that no Validator judged.

`POST /voice/speak` synthesized whatever text a caller holding the room key sent, in the
facilitator's own voice. No screen in the app ever called it, and every line the team
hears is either a validated turn or a pre-approved fixed line — so the route was a door
around containment with nobody on our side of it.
"""

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import router
from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import register_exception_handlers

PREFIX = "/api/internalization-room"
KEY = "sala-de-teste"


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(get_settings(), "internalization_room_api_key", KEY, raising=False)

    test_app = FastAPI()
    test_app.include_router(router, prefix=PREFIX)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    async with httpx.AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as c:
        yield c


async def test_a_room_key_cannot_make_the_facilitator_say_arbitrary_text(
    client: httpx.AsyncClient,
) -> None:
    said = await client.post(
        f"{PREFIX}/voice/speak",
        headers={"X-Room-Key": KEY},
        json={"text": "Bem-vindos.", "language": "pt"},
    )

    assert said.status_code == 405, said.text[:200]
