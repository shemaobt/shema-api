"""ENG-1412 — a frase told while a check lands still un-checks the passage it changed.

The chunks door reads the telling-back state, then waits on the transcriber, then captures.
A capture after a check undoes what the check left, and it decided that on the state it read
— so a check that passed during the transcription was seen by the capture's redo as a field
the capture had not touched, and the passage stood checked with a stretch the analyst never
read, which is all the release gate asks.

The check lands from a session of its own while the transcriber is still working, the way a
`terminei` from the other tablet would.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.internalization_room import back_translation as bt_api
from app.services.internalization_room.segments import final_segments
from app.services.internalization_room.sessions import (
    back_translation_of,
    get_session,
    save_back_translation,
)
from tests.release_harness import PREFIX, TABLET
from tests.room_harness import (
    nothing_is_read_ahead,
    rehearsed_in_parts_of,
    room_client,
    the_bucket_is_in_memory,
    the_room_speaks,
)


@pytest.fixture(autouse=True)
def voice(monkeypatch: pytest.MonkeyPatch) -> None:
    the_room_speaks(monkeypatch)
    nothing_is_read_ahead(monkeypatch)


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    the_bucket_is_in_memory(monkeypatch)
    async with room_client(db_session, monkeypatch) as room:
        yield room


async def test_a_frase_told_while_a_check_passes_leaves_the_passage_unchecked_not_checked(
    client,
    db_session: AsyncSession,
    rival_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, (part,) = await rehearsed_in_parts_of(db_session, [2])
    told = await final_segments(db_session, session.id)

    async def heard_while_a_check_passes(*_: Any, **__: Any) -> str:
        async with rival_factory() as checking_db:
            checking = await get_session(checking_db, session.id)
            state = back_translation_of(checking)
            state.checked = True
            state.analysed_segment_ids = [stretch.id for stretch in told]
            await save_back_translation(checking_db, checking, state)
        return "e Rute ficou com Noemi"

    monkeypatch.setattr(bt_api, "heard", heard_while_a_check_passes)

    answered = await client.post(
        f"{PREFIX}/sessions/{session.id}/back-translation/chunks",
        headers={"X-Room-Device": TABLET},
        data={
            "take_id": part.id,
            "starts_ms": str(told[-1].ends_ms),
            "ends_ms": str(told[-1].ends_ms + 1000),
        },
        files={"file": ("nova.m4a", b"uma frase nova durante a conferencia", "audio/mp4")},
    )
    assert answered.status_code == 200, answered.text

    async with rival_factory() as fresh_db:
        stored = back_translation_of(await get_session(fresh_db, session.id))
    assert stored.checked is False, (
        "a captura refeita sobre a conferência que passou mantinha o checked, e a passagem "
        "ficava conferida com uma frase que o analista nunca leu"
    )
