"""ENG-1303 — a turn tracks no practice, invitation or probe, and the stored history stays.

Every passage turn used to read what the voice had said and what the team answered back into
the session's comprehension column: an invitation the regex recognised named the next scene
owed a rehearsal, a «pronto» after it credited that scene as practised, and the probe the
room once forced was carried or dropped. Her room tracks none of it — the voice decides from
the conversation — so the column is left as it was stored, and a row that still holds an old
probe or practice list keeps it as history.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.internalization_room import sessions as sessions_api
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.sessions import get_session
from tests.release_harness import PREFIX, a_claimed_device, team_headers
from tests.room_harness import room_client, the_bucket_is_in_memory
from tests.tablet_turn_harness import the_room_opens, the_team_says, the_turn_is_scripted
from tests.text_seam_harness import ScriptedAgent

INVITATION = (
    "Uma fome chega, e uma família sai de Belém para os campos de Moabe. "
    "Agora ensaiem esta cena juntos na língua de vocês; quando terminarem, "
    "venham me contar em português o que vocês entenderam."
)

LEGACY = {
    "ledger": [],
    "active_probe": {
        "id": "probe-1",
        "checkpoint_ids": ["proposition:P03:P1"],
        "method": "micro_tellback",
        "purpose": "initial_check",
        "practice_scene_ids": [],
    },
    "practiced_scene_ids": ["S1"],
    "invited_scene_id": None,
}


@pytest.fixture()
def guide(monkeypatch: pytest.MonkeyPatch) -> ScriptedAgent:
    agent = ScriptedAgent([INVITATION, None, INVITATION, None])

    async def heard(*_: Any, **__: Any) -> HeardSpeech:
        return HeardSpeech(text="Pronto, terminamos. Já ensaiamos a cena.")

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


async def test_an_invitation_and_the_teams_pronto_leave_the_stored_comprehension_as_it_was(
    client, db_session, per_request, guide
) -> None:
    _team, tablet = await a_claimed_device(db_session)
    opened = await client.post(
        f"{PREFIX}/sessions",
        headers=team_headers(tablet),
        json={"language": "pt", "pericope": "P03"},
    )
    session_id = opened.json()["session_id"]
    async with per_request() as fresh:
        row = await get_session(fresh, session_id)
        row.comprehension = LEGACY
        await fresh.commit()

    await the_room_opens(client, tablet, session_id)
    await the_team_says(client, tablet, session_id, "turno-1")

    async with per_request() as fresh:
        stored = (await get_session(fresh, session_id)).comprehension
    assert stored == LEGACY, (
        "o turno reescreveu o estado de compreensão a partir do convite da voz e do «pronto»"
    )
