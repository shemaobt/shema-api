"""A recording the server assembled long ago is a **Part** like any other, read by its number.

The **Packet** carries one recording per part, the newest, and which recording is current is a
fact of the takes: a rehearsal take stored under a number an earlier take of the session
carries *is* that part again (ADR 0023). A part nobody told back is no blocker of its own any
more (ENG-1197): her check runs with it, and it still has to be heard.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.release_harness import ensaio_take
from tests.room_harness import (
    after,
    heard_every_part,
    press_terminei,
    rehearsed_in_parts,
    release_packet,
    room_client,
    stretch_on,
    the_analyst_reads,
    the_bucket_is_in_memory,
    the_room_speaks,
)


@pytest.fixture(autouse=True)
def analyst(monkeypatch: pytest.MonkeyPatch) -> None:
    """The analyst, reading clean, so a press of `terminei` leaves a check nothing is open on."""
    the_analyst_reads(monkeypatch)


@pytest.fixture(autouse=True)
def voice(monkeypatch: pytest.MonkeyPatch) -> None:
    """The Speaker and the synthesizer, so `terminei` answers without a model or a bucket."""
    the_room_speaks(monkeypatch)


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    """The room's routes, with the bucket in memory so an upload needs no storage."""
    the_bucket_is_in_memory(monkeypatch)
    async with room_client(db_session, monkeypatch) as room:
        yield room


async def _pressed_terminei(client: httpx.AsyncClient, db: AsyncSession, session_id: str) -> None:
    """Press `terminei` over the parts the session's stretches are standing on right now."""
    report = await heard_every_part(db, session_id)
    answered = await press_terminei(client, session_id, report=report)
    assert answered.status_code == 200, answered.text


async def test_an_old_composed_row_still_yields_one_take_per_number(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """A passage the server assembled, stored back when it did that, is a take like any other.

    The fixture is the state the **Rebuild** left behind while the room had one: a recording
    built around a corrected stretch, kept under the number of the recording it was built from,
    with that part's stretches re-pointed at the file that came out. Those rows are history and
    travel through the packet by the same rule as any take (ADR 0025).

    What the case holds is that such a row flows by the same rule as any take: it is the newest
    under two, therefore it is part two, and the packet carries one recording per number. It
    cannot hold that the scope is *read and ignored*, because nothing reads it — which is the
    state this slice leaves behind and the reason the row is unremarkable.
    """
    session, (one, two, three) = await rehearsed_in_parts(db_session, 3)
    told_on_two = await stretch_on(db_session, session, two)
    assembled = ensaio_take(
        session.id,
        scope="composed",
        ordinal=two.ordinal,
        sha256="r" * 64,
        created_at=after(two),
        project_id=session.project_id,
    )
    db_session.add(assembled)
    await db_session.commit()
    told_on_two.take_id = assembled.id
    await db_session.commit()
    await _pressed_terminei(client, db_session, session.id)

    audio = (await release_packet(db_session, session))["audio"]

    assert [take["ordinal"] for take in audio["rehearsal_takes"]] == [1, 2, 3]
    assert [take["take_id"] for take in audio["rehearsal_takes"]] == [
        one.id,
        assembled.id,
        three.id,
    ]


async def test_the_short_way_answers_no_composed_take(
    client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The answer to a correction names no passage the server built, because none is built.

    The key itself is gone rather than answered null: a reader finding it absent knows there is
    nothing of the kind to look for, where a null reads as a rebuilding that could not be done.
    """
    from app.api.internalization_room import segments as segments_api

    async def _heard(*_: Any, **__: Any) -> str:
        return "o trecho contado outra vez"

    monkeypatch.setattr(segments_api, "heard", _heard)
    session, (part,) = await rehearsed_in_parts(db_session, 1)
    told = await stretch_on(db_session, session, part)

    answered = await client.post(
        f"/api/internalization-room/sessions/{session.id}/segments/{told.id}/replace",
        headers={"X-Room-Device": "tablet-da-sala"},
        data={
            "take_id": part.id,
            "starts_ms": str(told.starts_ms),
            "ends_ms": str(told.ends_ms),
        },
        files={"file": ("de-novo.m4a", b"a equipe contou o trecho outra vez", "audio/mp4")},
    )

    assert answered.status_code == 200, answered.text
    assert "composed_take_id" not in answered.json()
