"""ENG-1303 — nothing the Guide reads names Refine, a red circle or the upper-right.

Her send-off sends the team to the Final Rehearsal through the orange dot at the top of the
screen. Our old instructions sent them to «the red-circle button in the upper-right» and
called the first rehearsal work prepared for OBT Refine, and the voice said both aloud. Her
body replaced ours, and what the room adds around it — her notes, the ledger, the earlier
passages, the moment — must not bring either back.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.internalization_room import sessions as sessions_api
from app.services.internalization_room.hearing import HeardSpeech
from tests.release_harness import PREFIX, a_claimed_device, team_headers
from tests.room_harness import room_client, the_bucket_is_in_memory
from tests.tablet_turn_harness import the_room_opens, the_team_says, the_turn_is_scripted
from tests.text_seam_harness import ScriptedAgent

OURS = ("refine", "red circle", "red-circle", "upper-right", "upper right", "círculo vermelho")


@pytest.fixture()
def guide(monkeypatch: pytest.MonkeyPatch) -> ScriptedAgent:
    agent = ScriptedAgent([])

    async def heard(*_: Any, **__: Any) -> HeardSpeech:
        return HeardSpeech(text="Terminamos todas as cenas. E agora, o que fazemos?")

    async def no_opening_ahead(*_: Any, **__: Any) -> None:
        return None

    the_turn_is_scripted(monkeypatch, heard=heard, model=agent)
    monkeypatch.setattr(sessions_api, "prepare_opening", no_opening_ahead)
    return agent


@pytest.fixture()
def per_request(test_engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture()
async def client(db_session: AsyncSession, per_request, guide, monkeypatch: pytest.MonkeyPatch):
    the_bucket_is_in_memory(monkeypatch)
    async with room_client(db_session, monkeypatch, per_request=per_request) as c:
        yield c


async def test_the_opening_and_a_turn_hand_the_guide_her_send_off_and_none_of_ours(
    client, db_session, guide
) -> None:
    _team, tablet = await a_claimed_device(db_session)
    opened = await client.post(
        f"{PREFIX}/sessions",
        headers=team_headers(tablet),
        json={"language": "pt", "pericope": "P03"},
    )
    session_id = opened.json()["session_id"]

    await the_room_opens(client, tablet, session_id)
    await the_team_says(client, tablet, session_id, "turno-1")

    read = [*guide.guide_systems, *guide.guide_inputs]
    assert len(guide.guide_systems) == 2
    assert all(
        "toquem no ponto laranja, no alto da tela" in system for system in guide.guide_systems
    )
    found = sorted({word for word in OURS for text in read if word in text.lower()})
    assert not found, f"o Guia lia de novo o que era nosso na despedida: {found}"
