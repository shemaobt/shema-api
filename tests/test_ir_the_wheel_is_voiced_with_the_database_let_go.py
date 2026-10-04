"""The wheel's passages are voiced with the database let go.

The route reads nothing of its own; the only read is the tablet's credential, which the gate
checks on the request's session. The synthesizer reads `in_transaction()` on that session each
time it is asked for a passage's line.
"""

from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.release_harness import PREFIX, a_claimed_device, team_headers
from tests.room_harness import room_client


async def test_a_tablet_with_a_credential_hears_the_wheel_voiced_with_the_read_let_go(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.api.internalization_room import passages as route

    _, credential = await a_claimed_device(db_session)
    held: list[bool] = []

    async def voices(text: str, **_: object) -> tuple[SimpleNamespace, bool]:
        held.append(db_session.in_transaction())
        return SimpleNamespace(key=f"linhas/{len(held)}.mp3"), False

    monkeypatch.setattr(route.room, "synthesize_facilitator_speech", voices)

    async with room_client(db_session, monkeypatch) as client:
        wheel: httpx.Response = await client.get(
            f"{PREFIX}/books/Ruth/passages",
            params={"language": "pt"},
            headers=team_headers(credential),
        )

    assert wheel.status_code == 200, wheel.text
    assert held and set(held) == {False}, (
        "a leitura da credencial abria a transação e a conexão ficava presa por todas as"
        " sínteses da roda"
    )
