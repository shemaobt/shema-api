import json
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.internalization_room.hearing import HeardSpeech
from tests.opening_harness import the_tablet_opens
from tests.release_harness import PREFIX, a_claimed_device, team_headers
from tests.room_harness import room_client
from tests.tablet_turn_harness import the_room_opens, the_team_says, the_turn_is_scripted

P = "P01"
OPENING = "Vamos começar pela Familiarização. Primeiro eu conto a passagem inteira."


class _Guide:
    def __init__(self) -> None:
        self.says = OPENING

    async def __call__(self, *, system_prompt: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return self.says


@pytest.fixture()
def guide(monkeypatch: pytest.MonkeyPatch) -> _Guide:
    scripted = _Guide()

    async def heard(*_: Any, **__: Any) -> HeardSpeech:
        return HeardSpeech(text="estamos prontos")

    the_turn_is_scripted(monkeypatch, heard=heard, model=scripted)
    return scripted


async def an_opened_session(client: httpx.AsyncClient, db_session: AsyncSession) -> tuple[str, str]:
    _team, tablet = await a_claimed_device(db_session)
    session_id = (await the_tablet_opens(client, tablet, {"pericope": P, "language": "pt"}))[
        "session_id"
    ]
    await the_room_opens(client, tablet, session_id)
    return tablet, session_id


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    async with room_client(db_session, monkeypatch) as c:
        yield c


async def test_the_opening_reply_tells_the_screen_the_room_is_in_the_familiarization(
    client: httpx.AsyncClient, db_session: AsyncSession, guide: _Guide
) -> None:
    _team, tablet = await a_claimed_device(db_session)
    session_id = (await the_tablet_opens(client, tablet, {"pericope": P, "language": "pt"}))[
        "session_id"
    ]

    opening = (await the_room_opens(client, tablet, session_id)).json()

    assert opening["moment"] == {"at": "familiarization", "part": None, "parts": 4}, (
        "a resposta da abertura não dizia à tela em que momento a sala estava"
    )


async def test_a_reply_that_opens_scene_two_tells_the_screen_internalization_of_part_two(
    client: httpx.AsyncClient, db_session: AsyncSession, guide: _Guide
) -> None:
    tablet, session_id = await an_opened_session(client, db_session)
    guide.says = "Muito bem. Vamos pra Internalização da cena 2."

    reply = (await the_team_says(client, tablet, session_id, "segundo")).json()

    assert reply["moment"] == {"at": "internalization", "part": 2, "parts": 4}, (
        "a tela ficava na Familiarização depois que a voz abriu a cena 2"
    )


async def test_the_session_read_says_where_the_last_reply_left_the_room_and_nothing_before_it(
    client: httpx.AsyncClient, db_session: AsyncSession, guide: _Guide
) -> None:
    _team, tablet = await a_claimed_device(db_session)
    opened = await the_tablet_opens(client, tablet, {"pericope": P, "language": "pt"})
    await the_room_opens(client, tablet, opened["session_id"])
    guide.says = "Muito bem. Vamos pra Internalização da cena 2."
    await the_team_says(client, tablet, opened["session_id"], "segundo")

    read = await client.get(
        f"{PREFIX}/sessions/{opened['session_id']}", headers=team_headers(tablet)
    )

    assert opened["moment"] is None, "uma sessão que ainda não ouviu a voz já tinha momento"
    assert read.json()["moment"] == {"at": "internalization", "part": 2, "parts": 4}, (
        "o tablet que voltava para a sessão não sabia em que momento a sala estava"
    )
