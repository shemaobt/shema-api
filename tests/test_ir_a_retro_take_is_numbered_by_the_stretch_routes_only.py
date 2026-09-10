"""A retro take is numbered by the stretch routes only, and the number is called ordinal.

ENG-639 made a back-translation take carry the ordinal of the stretch it tells, written where
a stretch gets its ordinal. It did not reach the generic takes route, which wrote down
whatever number the tablet sent — the position in the tablet's own list — so the packet's
`retro_takes` carried two numberings under one field. A retro take kept through that route
now carries no number at all: a recording that captured no stretch claims no place in the
telling-back.

The column and the fields that hold that number are called `ordinal`, because that is what
they hold: the persistent number of a stretch. **Chunk** is the ephemeral position in one
reading of the analyst, and never was this. The form still accepts `chunk_index`, but the
takes response answers with `ordinal` alone now: ENG-872 takes the alias away.
"""

from __future__ import annotations

import base64
import uuid
from typing import Any

import httpx
import pytest
from google_crc32c import Checksum
from httpx import ASGITransport
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

import app.db.models  # noqa: F401  (populates Base.metadata with every table)
from app.core.database import Base
from app.db.models.internalization_room import IRTake, IRTakeKind
from app.services import internalization_room as room
from app.services.platform.storage import StoredObject
from tests.test_ir_a_take_is_numbered_by_its_stretch import (
    DEVICE,
    KEY,
    PASSAGE,
    PREFIX,
    _a_failed_capture_then_two_good_ones,
    _open_session,
    _ready_for_release,
    _record,
)
from tests.test_ir_project_id_migration import _columns, _run_alembic, _scalar

REVISION = "20260910_take01"
PREVIOUS_REVISION = "20260908_arr02"


class MemoryStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def get(self, key: str) -> bytes | None:
        return self.objects.get(key)

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = data

    async def stat(self, key: str) -> StoredObject | None:
        stored = self.objects.get(key)
        if stored is None:
            return None
        checksum = Checksum()
        checksum.update(stored)
        return StoredObject(
            size=len(stored), crc32c=base64.b64encode(checksum.digest()).decode("ascii")
        )


@pytest.fixture()
async def bucket(monkeypatch: pytest.MonkeyPatch) -> MemoryStore:
    from app.services.internalization_room import takes as takes_service

    store = MemoryStore()
    monkeypatch.setattr(takes_service, "_store", lambda *_, **__: store)
    return store


@pytest.fixture()
async def client(db_session: AsyncSession, bucket: MemoryStore, monkeypatch: pytest.MonkeyPatch):
    """The room's own routes, with the transcriber and the bucket held still.

    `client.said` queues what the transcriber will answer, one entry per capture.
    """
    from fastapi import FastAPI

    from app.api.internalization_room import back_translation as bt_api
    from app.api.internalization_room import router
    from app.api.internalization_room import segments as segments_api
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    monkeypatch.setattr(get_settings(), "internalization_room_api_key", KEY, raising=False)

    said: list[str] = []

    async def _transcribe(*_: Any, **__: Any) -> str:
        return said.pop(0) if said else "algo que a equipe contou"

    monkeypatch.setattr(bt_api, "heard", _transcribe)
    monkeypatch.setattr(segments_api, "heard", _transcribe)

    test_app = FastAPI()
    test_app.include_router(router, prefix=PREFIX)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        c.said = said  # type: ignore[attr-defined]
        yield c


async def _keep(
    client: httpx.AsyncClient,
    session_id: str,
    *,
    kind: IRTakeKind,
    chunk_index: int,
    audio: bytes,
) -> httpx.Response:
    """Post one take to the generic route, with the number the tablet believes it has."""
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/takes",
        headers={"X-Room-Key": KEY, "X-Room-Device": DEVICE},
        data={"kind": kind.value, "scope": PASSAGE, "chunk_index": str(chunk_index)},
        files={"file": ("gravacao.m4a", audio, "audio/mp4")},
    )


async def _take_by_id(db: AsyncSession, take_id: str) -> IRTake:
    """The row as the database holds it, not as the session still remembers it.

    The route wrote through this same session, so an instance left unexpired would answer
    from the identity map and the assertion would pass even if nothing had reached the
    column.
    """
    db.expire_all()
    result = await db.execute(select(IRTake).where(IRTake.id == take_id))
    return result.scalar_one()


async def _listed(client: httpx.AsyncClient, session_id: str, take_id: str) -> dict[str, Any]:
    listed = await client.get(f"{PREFIX}/sessions/{session_id}/takes", headers={"X-Room-Key": KEY})
    assert listed.status_code == 200, listed.text
    return next(take for take in listed.json()["takes"] if take["take_id"] == take_id)


# ---------------------------------------------------------------------------
# 1. The generic route keeps no number for a retro take
# ---------------------------------------------------------------------------


async def test_the_generic_route_keeps_no_number_for_a_retro_take(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session_id = await _open_session(client)
    await _record(client, session_id, b"a equipe ensaiou a passagem inteira")

    kept = await _keep(
        client,
        session_id,
        kind=IRTakeKind.RETRO,
        chunk_index=7,
        audio=b"um trecho contado de volta pela rota generica",
    )
    assert kept.status_code == 200, kept.text

    take_id = kept.json()["take_id"]
    assert kept.json()["ordinal"] is None, (
        "a posição que o tablet manda não é o ordinal de trecho nenhum"
    )
    assert (await _take_by_id(db_session, take_id)).ordinal is None

    listed = await _listed(client, session_id, take_id)
    assert listed["ordinal"] is None
    assert "chunk_index" not in listed, "o apelido do tablet saiu da resposta"


# ---------------------------------------------------------------------------
# 2. A rehearsal take keeps the number it was sent with
# ---------------------------------------------------------------------------


async def test_the_generic_route_keeps_a_rehearsal_takes_number(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Only a retro take loses the number: the rule is about telling a stretch back.

    A rehearsal take is a part of the passage, and its number is how the tablet finds again,
    on resume, which part a rebuilt recording answers for.
    """
    session_id = await _open_session(client)

    kept = await _keep(
        client,
        session_id,
        kind=IRTakeKind.ENSAIO,
        chunk_index=3,
        audio=b"a terceira parte do ensaio",
    )
    assert kept.status_code == 200, kept.text

    take_id = kept.json()["take_id"]
    assert (await _take_by_id(db_session, take_id)).ordinal == 3

    listed = await _listed(client, session_id, take_id)
    assert listed["ordinal"] == 3
    assert "chunk_index" not in listed, "o apelido do tablet saiu da resposta"


# ---------------------------------------------------------------------------
# 3. The packet says ordinal and never chunk_index
# ---------------------------------------------------------------------------


async def test_the_packet_says_ordinal_and_never_chunk_index(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session_id = await _a_failed_capture_then_two_good_ones(client)
    session = await room.get_session(db_session, session_id)

    artifact = await _ready_for_release(db_session, session)

    retro_takes = artifact["back_translation"]["retro_takes"]
    assert [take["ordinal"] for take in retro_takes] == [None, 1, 2]

    for take in [*retro_takes, *artifact["audio"]["rehearsal_takes"]]:
        assert "chunk_index" not in take, (
            "o pacote viaja para o Refine com o nome do que a coluna guarda"
        )


# ---------------------------------------------------------------------------
# 4. The migration renames the column both ways
# ---------------------------------------------------------------------------


async def _built_and_seeded(database_url: str) -> str:
    """The post-migration schema with one take already numbered.

    Alembic's full chain does not run on SQLite, so the shape is the one
    `test_ir_project_id_migration.py` uses: build from `Base.metadata`, which is the
    post-migration schema, stamp it as applied, and walk down and back up. A rename that
    quietly dropped the column would pass a test that only counted names, so the value goes
    in first and is read on both sides of the walk.
    """
    engine = create_async_engine(database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    take_id = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO ir_takes (id, session_id, device_id, pericope, kind, scope,"
                " ordinal, storage_key, size_bytes, sha256, crc32c, content_type, created_at)"
                " VALUES (:id, 'sessao-1', 'tablet-1', 'P01', 'retro', 'P01', 4, 'chave', 1,"
                " 'sha', 'crc', 'audio/mp4', '2026-09-10 00:00:00')"
            ),
            {"id": take_id},
        )
    await engine.dispose()
    return take_id


@pytest.fixture()
async def renamed_database(tmp_path) -> dict[str, str]:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'ir_takes_ordinal.db'}"
    take_id = await _built_and_seeded(database_url)

    stamped = _run_alembic(database_url, "stamp", REVISION)
    assert stamped.returncode == 0, stamped.stderr

    return {"url": database_url, "take_id": take_id}


async def test_the_migration_renames_the_column_both_ways_without_losing_the_number(
    renamed_database,
) -> None:
    url = renamed_database["url"]
    take_id = renamed_database["take_id"]

    at_revision = await _columns(url, "ir_takes")
    assert "ordinal" in at_revision
    assert "chunk_index" not in at_revision

    down = _run_alembic(url, "downgrade", PREVIOUS_REVISION)
    assert down.returncode == 0, down.stderr

    below = await _columns(url, "ir_takes")
    assert "chunk_index" in below
    assert "ordinal" not in below
    assert (
        await _scalar(url, "SELECT chunk_index FROM ir_takes WHERE id = :id", {"id": take_id}) == 4
    ), "o rename perdeu o número na descida"

    up = _run_alembic(url, "upgrade", REVISION)
    assert up.returncode == 0, up.stderr

    back = await _columns(url, "ir_takes")
    assert "ordinal" in back
    assert "chunk_index" not in back
    assert (
        await _scalar(url, "SELECT ordinal FROM ir_takes WHERE id = :id", {"id": take_id}) == 4
    ), "o rename perdeu o número na volta"
