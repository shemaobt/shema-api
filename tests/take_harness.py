"""The room's take and chunk routes, driven over HTTP the way the tablet drives them.

A case about how a take is numbered has to reach the number the way the app does — through
the routes that store audio — because the number is written on the way in. These are the
calls that get a session to that state, and nothing here asserts anything: what a case
concludes from the rows it reads is the case's own.

Fixtures are not exported, for the reason `room_harness` gives: what travels is the builder
and each module keeps the three-line fixture that calls it.

The room key and the prefix are declared here rather than read off `release_harness`, which
also has them. A take is stored and numbered long before any release exists, and nothing here
touches one: reading the constants from there would put the release scaffold — the project,
the device claim, four bakers — behind every case about how a take gets its number, and the
first reader would have to open that file to find out why.
"""

from __future__ import annotations

import httpx

from app.db.models.internalization_room import IRTakeKind

PREFIX = "/api/internalization-room"
KEY = "sala-de-teste"
DEVICE = "tablet-da-equipe-1"
PASSAGE = "P01"


async def open_session(client: httpx.AsyncClient) -> str:
    created = await client.post(
        f"{PREFIX}/sessions", headers={"X-Room-Key": KEY}, json={"pericope": PASSAGE}
    )
    assert created.status_code == 200, created.text
    return str(created.json()["session_id"])


async def record(client: httpx.AsyncClient, session_id: str, audio: bytes) -> str:
    kept = await client.post(
        f"{PREFIX}/sessions/{session_id}/takes",
        headers={"X-Room-Key": KEY, "X-Room-Device": DEVICE},
        data={"kind": IRTakeKind.ENSAIO.value, "scope": PASSAGE},
        files={"file": ("tomada.m4a", audio, "audio/mp4")},
    )
    assert kept.status_code == 200, kept.text
    return str(kept.json()["take_id"])


async def tell_back(
    client: httpx.AsyncClient,
    session_id: str,
    *,
    take_id: str,
    starts_ms: int,
    ends_ms: int,
    audio: bytes,
) -> httpx.Response:
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/back-translation/chunks",
        headers={"X-Room-Key": KEY, "X-Room-Device": DEVICE},
        data={"take_id": take_id, "starts_ms": str(starts_ms), "ends_ms": str(ends_ms)},
        files={"file": ("trecho.m4a", audio, "audio/mp4")},
    )


async def a_failed_capture_then_two_good_ones(client: httpx.AsyncClient) -> str:
    """One session: a stretch told back three times, the first attempt inaudible.

    The retry over the same slice is what takes the first place; the third call is a new
    stretch. Three different byte strings, so the dedupe by hash never enters into it.
    """
    session_id = await open_session(client)
    take_id = await record(client, session_id, b"a equipe ensaiou a passagem inteira")

    client.said.extend(["", "Noemi ouve que", "e decide voltar"])  # type: ignore[attr-defined]
    await tell_back(
        client, session_id, take_id=take_id, starts_ms=0, ends_ms=9000, audio=b"tentativa muda"
    )
    await tell_back(
        client, session_id, take_id=take_id, starts_ms=0, ends_ms=9000, audio=b"tentativa boa"
    )
    await tell_back(
        client, session_id, take_id=take_id, starts_ms=9000, ends_ms=21000, audio=b"terceiro trecho"
    )
    return session_id
