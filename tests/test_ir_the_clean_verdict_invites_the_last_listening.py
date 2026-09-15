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
    played_every_part,
    press_terminei,
    rehearsed_in_parts,
    room_client,
    the_analyst_reads,
    the_room_speaks,
)

#: What the Speaker double answers with. The case is about the instruction the room gave, so
#: the words that come back are fixed and only have to prove the room voiced them.
CLEAN_DRAFT = "Vocês contaram bem."

#: The promise of another round of telling back. There is none after this turn, and the last
#: step the team is invited to is not one.
CONTINUES_TELLING_BACK = "finish the telling-back again"


@pytest.fixture(autouse=True)
def analyst(monkeypatch: pytest.MonkeyPatch) -> Analyst:
    return the_analyst_reads(monkeypatch)


@pytest.fixture()
def briefs() -> list[str]:
    return []


@pytest.fixture(autouse=True)
def spoken(monkeypatch: pytest.MonkeyPatch, briefs: list[str]) -> list[str]:
    return the_room_speaks(monkeypatch, briefs=briefs)


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    async with room_client(db_session, monkeypatch) as room:
        yield room


@pytest.mark.asyncio
async def test_a_clean_check_orders_the_last_listening_and_the_approval(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    briefs: list[str],
    spoken: list[str],
) -> None:
    """The rule, at the door: the passage confers and the Speaker is told to name one step."""
    session, parts = await rehearsed_in_parts(db_session, 3)

    answered = await press_terminei(
        client, session.id, report=played_every_part([part.id for part in parts])
    )

    assert answered.status_code == 200, answered.text
    assert answered.json()["checked"] is True
    assert "listen to" in briefs[-1]
    assert "once more" in briefs[-1]
    assert "approve" in briefs[-1]
    assert "final draft" in briefs[-1]
    assert CONTINUES_TELLING_BACK not in briefs[-1]
    assert spoken == [CLEAN_DRAFT]
