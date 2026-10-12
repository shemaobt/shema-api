"""ENG-1378 — a name said in a turn moves its bead with that turn's own reply.

Her room checks names inside every turn, once the reply is made (her `oralTurn.ts:88-90`,
PRD ch.13): a being, place, object or time the team names — «Noemi» for Naomi — is engaged,
one the voice names is surfaced, and the turn is saved and answered with them
(`route.ts:247`). Ours left every bead to the classifier that runs after the reply has
shipped, so the beads lagged a turn behind for names, and a classifier that failed moved
none of them at all.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.internalization_room import sessions as sessions_api
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.sessions import get_session
from tests.release_harness import PREFIX, a_claimed_device, team_headers
from tests.room_harness import room_client, the_bucket_is_in_memory
from tests.tablet_turn_harness import the_room_opens, the_team_says, the_turn_is_scripted

OPENING = "Vamos ouvir uma história juntos."
REPLY = "Isso. Contem mais."


@pytest.fixture()
def voice_says() -> list[str]:
    return [OPENING, REPLY]


@pytest.fixture()
def team_says(monkeypatch: pytest.MonkeyPatch, voice_says: list[str]) -> list[str]:
    said = ["A Noemi ficou."]

    async def heard(*_: Any, **__: Any) -> HeardSpeech:
        return HeardSpeech(text=said[0])

    async def model(*, system_prompt: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return voice_says.pop(0)

    async def no_opening_ahead(*_: Any, **__: Any) -> None:
        return None

    the_turn_is_scripted(monkeypatch, heard=heard, model=model)
    monkeypatch.setattr(sessions_api, "prepare_opening", no_opening_ahead)
    return said


@pytest.fixture()
def per_request(test_engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture()
async def client(db_session: AsyncSession, per_request, team_says, monkeypatch):
    the_bucket_is_in_memory(monkeypatch)
    async with room_client(db_session, monkeypatch, per_request=per_request) as c:
        yield c


async def _a_p01_session(client, db_session) -> tuple[str, str]:
    _team, tablet = await a_claimed_device(db_session)
    opened = await client.post(
        f"{PREFIX}/sessions",
        headers=team_headers(tablet),
        json={"language": "pt", "pericope": "P01"},
    )
    return tablet, opened.json()["session_id"]


async def _stored(per_request, session_id: str) -> dict[str, str]:
    async with per_request() as fresh:
        return dict((await get_session(fresh, session_id)).coverage_state or {})


async def test_the_team_saying_noemi_engages_naomi_on_that_turns_reply_with_no_classifier(
    client, db_session, per_request
) -> None:
    tablet, session_id = await _a_p01_session(client, db_session)
    await the_room_opens(client, tablet, session_id)

    answered = await the_team_says(client, tablet, session_id, "turno-1")

    stored = await _stored(per_request, session_id)
    assert [stored.get(f"being:S{scene}:B3") for scene in (1, 2, 3)] == ["engaged"] * 3, (
        "a equipe dizia «Noemi» e a conta de Noemi só andava quando o classificador rodasse"
    )
    assert answered.json()["coverage"]["engaged"] >= 3, (
        "a resposta do turno voltava com as contas de antes do nome dito"
    )


async def test_the_voice_naming_elimelech_surfaces_him_and_leaves_naomi_engaged(
    client, db_session, per_request, voice_says
) -> None:
    voice_says[1] = "E a Noemi foi com o Elimeleque."
    tablet, session_id = await _a_p01_session(client, db_session)
    await the_room_opens(client, tablet, session_id)

    await the_team_says(client, tablet, session_id, "turno-1")

    stored = await _stored(per_request, session_id)
    assert [stored.get(f"being:S{scene}:B2") for scene in (1, 2)] == ["surfaced"] * 2, (
        "a voz dizia Elimeleque na resposta e a conta dele ficava como não tocada"
    )
    assert stored.get("being:S1:B3") == "engaged", (
        "Noemi, dita pela equipe, descia para surfaced quando a voz também a nomeava"
    )
