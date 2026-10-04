"""A clean check ends by inviting the last listening and the approval, through the real door.

The service cases pin the ordered closing where it is chosen. This one presses `terminei` on a
session that owes nothing — told back whole, heard whole, nothing found — and reads what the
room actually put in front of the Speaker on that turn, because the closing travels through the
verdict round, the turn and the template before it gets there, and a step dropped anywhere on
that way is a team left with a checked passage and no last step named.
"""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.room_harness import (
    Analyst,
    Room,
    played_every_part,
    press_terminei,
    rehearsed_in_parts,
    room_client,
    the_analyst_reads,
    the_room_speaks,
)
from tests.turn_harness import CONTINUES_TELLING_BACK, INVITATION_WORDS


@pytest.fixture(autouse=True)
def analyst(monkeypatch: pytest.MonkeyPatch) -> Analyst:
    return the_analyst_reads(monkeypatch)


@pytest.fixture(autouse=True)
def room(monkeypatch: pytest.MonkeyPatch) -> Room:
    return the_room_speaks(monkeypatch)


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    async with room_client(db_session, monkeypatch) as door:
        yield door


async def test_a_clean_check_orders_the_last_listening_and_the_approval(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    room: Room,
) -> None:
    """The rule, at the door: the passage confers and the Speaker is told to name one step.

    What the room said is read off the route's own answer and off the count of lines voiced,
    never off the words: the double was told what to say, so an assertion on them would be
    the case agreeing with its own fixture.
    """
    session, parts = await rehearsed_in_parts(db_session, 3)

    answered = await press_terminei(
        client, session.id, report=played_every_part([part.id for part in parts])
    )

    assert answered.status_code == 200, answered.text
    assert answered.json()["checked"] is True
    for word in INVITATION_WORDS:
        assert word in room.briefs[-1]
    assert CONTINUES_TELLING_BACK not in room.briefs[-1]
    assert answered.json()["used_fail_safe"] is False
    assert len(room.said) == 1
