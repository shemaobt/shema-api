"""A telling-back is kept in the bucket and transcribed with the database let go.

The chunk route and the stretch replacement both store the bytes and then ask the transcriber,
and both used to do it inside the transaction their reads opened. The bucket and the
transcriber read `in_transaction()` on the request's own session when they are called.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import httpx
import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.services.platform.storage import StoredObject
from tests.hard_stretch_harness import MemoryStore
from tests.release_harness import KEY, PREFIX, TABLET
from tests.room_harness import PART_MS, rehearsed_in_parts, room_client, stretch_on


class _WatchedBucket(MemoryStore):
    def __init__(self, db: AsyncSession, held: dict[str, bool]) -> None:
        super().__init__()
        self.db = db
        self.held = held

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.held["put"] = self.db.in_transaction()
        await super().put(key, data, content_type)

    async def stat(self, key: str) -> StoredObject | None:
        self.held["stat"] = self.db.in_transaction()
        return await super().stat(key)


@pytest.fixture()
def held(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> dict[str, bool]:
    from app.api.internalization_room import back_translation as bt_api
    from app.api.internalization_room import segments as segments_api
    from app.services.internalization_room import takes as takes_service

    seen: dict[str, bool] = {}
    bucket = _WatchedBucket(db_session, seen)

    async def heard(*_: Any, **__: Any) -> str:
        seen["stt"] = db_session.in_transaction()
        return "Noemi voltou com Rute"

    monkeypatch.setattr(takes_service, "_store", lambda *_, **__: bucket)
    monkeypatch.setattr(bt_api, "heard", heard)
    monkeypatch.setattr(segments_api, "heard", heard)
    return seen


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    async with room_client(db_session, monkeypatch) as door:
        yield door


async def test_a_stretch_told_back_again_is_kept_and_heard_with_the_database_let_go(
    client: httpx.AsyncClient, db_session: AsyncSession, held: dict[str, bool]
) -> None:
    session, (part,) = await rehearsed_in_parts(db_session, 1)

    told = await client.post(
        f"{PREFIX}/sessions/{session.id}/back-translation/chunks",
        headers={"X-Room-Key": KEY, "X-Room-Device": TABLET},
        data={
            "take_id": part.id,
            "starts_ms": "0",
            "ends_ms": str(PART_MS),
            "retelling": "true",
        },
        files={"file": ("trecho.m4a", b"a equipe contou de novo", "audio/mp4")},
    )

    assert told.status_code == 200, told.text
    assert told.json()["captured"] is True
    assert held == {"put": False, "stat": False, "stt": False}, (
        "as leituras do trecho abriam a transação e a conexão ficava presa pelo balde e pelo"
        " transcritor"
    )


async def test_a_stretch_replaced_is_kept_and_heard_with_the_database_let_go(
    client: httpx.AsyncClient, db_session: AsyncSession, held: dict[str, bool]
) -> None:
    session, (part,) = await rehearsed_in_parts(db_session, 1)
    stretch = await stretch_on(db_session, session, part)

    replaced = await client.post(
        f"{PREFIX}/sessions/{session.id}/segments/{stretch.id}/replace",
        headers={"X-Room-Key": KEY, "X-Room-Device": TABLET},
        data={"take_id": part.id, "starts_ms": "0", "ends_ms": str(PART_MS)},
        files={"file": ("trecho.m4a", b"a equipe contou outra vez", "audio/mp4")},
    )

    assert replaced.status_code == 200, replaced.text
    assert replaced.json()["captured"] is True
    assert held == {"put": False, "stat": False, "stt": False}, (
        "a troca do trecho transcrevia com a transação que o refresh do take reabria"
    )


async def test_a_telling_sent_again_is_heard_with_the_database_let_go_not_under_its_lookup(
    client: httpx.AsyncClient, db_session: AsyncSession, held: dict[str, bool]
) -> None:
    session, (part,) = await rehearsed_in_parts(db_session, 1)
    again = {
        "take_id": part.id,
        "starts_ms": "0",
        "ends_ms": str(PART_MS),
        "retelling": "true",
    }
    audio = {"file": ("trecho.m4a", b"a equipe contou de novo", "audio/mp4")}
    route = f"{PREFIX}/sessions/{session.id}/back-translation/chunks"
    headers = {"X-Room-Key": KEY, "X-Room-Device": TABLET}
    first = await client.post(route, headers=headers, data=again, files=audio)
    assert first.status_code == 200, first.text
    held.clear()

    resent = await client.post(route, headers=headers, data=again, files=audio)

    assert resent.status_code == 200, resent.text
    assert held == {"stt": False}, (
        "o reenvio achava o take já guardado e transcrevia com a busca pela chave ainda aberta"
    )


async def test_a_replacement_sent_again_is_heard_with_the_database_let_go_not_under_its_lookup(
    client: httpx.AsyncClient, db_session: AsyncSession, held: dict[str, bool]
) -> None:
    session, (part,) = await rehearsed_in_parts(db_session, 1)
    stretch = await stretch_on(db_session, session, part)
    headers = {"X-Room-Key": KEY, "X-Room-Device": TABLET}
    slice_ = {"take_id": part.id, "starts_ms": "0", "ends_ms": str(PART_MS)}
    audio = {"file": ("trecho.m4a", b"a equipe contou outra vez", "audio/mp4")}
    first = await client.post(
        f"{PREFIX}/sessions/{session.id}/segments/{stretch.id}/replace",
        headers=headers,
        data=slice_,
        files=audio,
    )
    assert first.status_code == 200, first.text
    standing = await stretch_on(db_session, session, part)
    held.clear()

    resent = await client.post(
        f"{PREFIX}/sessions/{session.id}/segments/{standing.id}/replace",
        headers=headers,
        data=slice_,
        files=audio,
    )

    assert resent.status_code == 200, resent.text
    assert held == {"stt": False}, (
        "a troca reenviada achava o take já guardado e transcrevia com a busca ainda aberta"
    )


@contextmanager
def _checkouts(test_engine: AsyncEngine) -> Iterator[list[object]]:
    counted: list[object] = []

    def _count(connection: object, *_: object) -> None:
        counted.append(connection)

    event.listen(test_engine.sync_engine, "checkout", _count)
    try:
        yield counted
    finally:
        event.remove(test_engine.sync_engine, "checkout", _count)


async def test_a_stretch_told_back_again_takes_three_connections_not_four(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    test_engine: AsyncEngine,
    held: dict[str, bool],
) -> None:
    session, (part,) = await rehearsed_in_parts(db_session, 1)
    await db_session.commit()

    with _checkouts(test_engine) as checkouts:
        told = await client.post(
            f"{PREFIX}/sessions/{session.id}/back-translation/chunks",
            headers={"X-Room-Key": KEY, "X-Room-Device": TABLET},
            data={
                "take_id": part.id,
                "starts_ms": "0",
                "ends_ms": str(PART_MS),
                "retelling": "true",
            },
            files={"file": ("trecho.m4a", b"a equipe contou de novo", "audio/mp4")},
        )

    assert told.status_code == 200, told.text
    assert len(checkouts) == 3, (
        "o refresh do take recém-gravado reabria uma conexão só para reler o que o INSERT já"
        " tinha devolvido"
    )


async def test_a_stretch_replaced_takes_four_connections_not_five(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    test_engine: AsyncEngine,
    held: dict[str, bool],
) -> None:
    session, (part,) = await rehearsed_in_parts(db_session, 1)
    stretch = await stretch_on(db_session, session, part)
    await db_session.commit()

    with _checkouts(test_engine) as checkouts:
        replaced = await client.post(
            f"{PREFIX}/sessions/{session.id}/segments/{stretch.id}/replace",
            headers={"X-Room-Key": KEY, "X-Room-Device": TABLET},
            data={"take_id": part.id, "starts_ms": "0", "ends_ms": str(PART_MS)},
            files={"file": ("trecho.m4a", b"a equipe contou outra vez", "audio/mp4")},
        )

    assert replaced.status_code == 200, replaced.text
    assert len(checkouts) == 4, (
        "o refresh do take recém-gravado reabria uma conexão só para reler o que o INSERT já"
        " tinha devolvido"
    )
