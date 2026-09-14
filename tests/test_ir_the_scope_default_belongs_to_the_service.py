"""The scope a telling-back is stored under is defaulted where the rule lives, not at a door.

Two doors reach the same capture — the tablet's chunks route and the text seam — and both
wrote the same default onto the persisted state before calling it. A default on state that is
written to the database is a business rule, and a rule copied into every caller is a rule that
holds until somebody opens a third door (ADR 0009).

Both cases go in through the door they are about and read the scope back out of the row. A
call straight to the service would pass with the routers still writing it themselves, which
is the arrangement these cases exist to refuse; and reading the state object the case handed
in would pass with nothing ever reaching the column.
"""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession, IRTakeKind
from tests.room_harness import (
    KEY,
    PREFIX,
    P,
    room_client,
    the_analyst_reads,
    the_bucket_is_in_memory,
    the_room_speaks,
    the_transcriber_says,
)

DEVICE = "tablet-da-equipe-1"
RUNNER_KEY = "runner-de-teste"
SEAM = f"{PREFIX}/text-seam/back-translation"
SEAM_PASSAGE = "P02"
CLIPS = [{"key": "S1", "durationMs": 20000}]


@pytest.fixture(autouse=True)
def room(monkeypatch: pytest.MonkeyPatch) -> None:
    the_analyst_reads(monkeypatch)
    the_room_speaks(monkeypatch)
    the_bucket_is_in_memory(monkeypatch)


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    the_transcriber_says(monkeypatch, ["Noemi mandou Rute voltar."])
    async with room_client(db_session, monkeypatch, runner_key=RUNNER_KEY) as room:
        yield room


async def _scope_in_the_row(db: AsyncSession, session_id: str) -> str:
    stored = await db.execute(
        select(IRSession)
        .where(IRSession.id == session_id)
        .execution_options(populate_existing=True)
    )
    return str((stored.scalar_one().back_translation or {}).get("scope", ""))


@pytest.mark.asyncio
async def test_the_chunks_door_stores_the_scope_the_service_defaults(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """A stretch told back from a tablet leaves the state naming the session's passage."""
    opened = await client.post(
        f"{PREFIX}/sessions", headers={"X-Room-Key": KEY}, json={"pericope": P, "language": "pt"}
    )
    assert opened.status_code == 200, opened.text
    session_id = opened.json()["session_id"]

    kept = await client.post(
        f"{PREFIX}/sessions/{session_id}/takes",
        headers={"X-Room-Key": KEY, "X-Room-Device": DEVICE},
        data={"kind": IRTakeKind.ENSAIO.value, "scope": "passagem-inteira"},
        files={"file": ("ensaio.m4a", b"a equipe ensaiou a passagem inteira", "audio/mp4")},
    )
    assert kept.status_code == 200, kept.text

    told = await client.post(
        f"{PREFIX}/sessions/{session_id}/back-translation/chunks",
        headers={"X-Room-Key": KEY, "X-Room-Device": DEVICE},
        data={"take_id": kept.json()["take_id"], "starts_ms": "0", "ends_ms": "9000"},
        files={"file": ("trecho.m4a", b"um trecho contado", "audio/mp4")},
    )

    assert told.status_code == 200, told.text
    assert await _scope_in_the_row(db_session, session_id) == P


@pytest.mark.asyncio
async def test_the_seam_door_stores_the_scope_the_service_defaults(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """And so does a frase entering as text through her runner's door."""
    declared = await client.post(
        f"{SEAM}/session",
        json={"pericopeId": SEAM_PASSAGE, "language": "Brazilian Portuguese", "clips": CLIPS},
    )
    assert declared.status_code == 200, declared.text
    session_id = declared.json()["sessionId"]

    played = await client.post(
        f"{SEAM}/round",
        json={
            "sessionId": session_id,
            "frases": [
                {
                    "clipKey": "S1",
                    "coversFrom": 0,
                    "coversTo": 10,
                    "text": "Noemi ouviu que o Senhor tinha dado pão ao seu povo.",
                }
            ],
        },
    )

    assert played.status_code == 200, played.text
    assert await _scope_in_the_row(db_session, session_id) == SEAM_PASSAGE
