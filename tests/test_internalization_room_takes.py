"""The audio the room is not allowed to lose.

The conversation's audio is thrown away once it is transcribed, and that is right: the record
there is the text. The ensaio take and the back-translation chunks are the opposite — the
recording is the work. Until now they existed only on the tablet, so a device that broke took
the session with it.
"""

import base64

import pytest
from google_crc32c import Checksum
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.db.models.internalization_room import IRTakeKind
from app.services.internalization_room import takes as service

DEVICE = "tablet-da-equipe-1"
AUDIO = b"a equipe contou a passagem inteira"


class MemoryStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.writes = 0

    async def get(self, key: str) -> bytes | None:
        return self.objects.get(key)

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.writes += 1
        self.objects[key] = data


class RefusingStore(MemoryStore):
    async def put(self, key: str, data: bytes, content_type: str) -> None:
        raise RuntimeError("o bucket recusou")


async def _keep(db: AsyncSession, store: MemoryStore, *, audio: bytes = AUDIO):
    return await service.store_take(
        db,
        session_id="sessao-1",
        device_id=DEVICE,
        pericope="P03",
        kind=IRTakeKind.ENSAIO,
        scope="passagem-inteira",
        audio=audio,
        store=store,
    )


@pytest.mark.asyncio
async def test_the_bytes_that_come_back_are_the_bytes_that_went_in(db_session: AsyncSession):
    store = MemoryStore()

    take = await _keep(db_session, store)

    assert store.objects[take.storage_key] == AUDIO


@pytest.mark.asyncio
async def test_the_checksums_describe_the_stored_bytes(db_session: AsyncSession):
    store = MemoryStore()

    take = await _keep(db_session, store)

    expected = Checksum()
    expected.update(AUDIO)
    assert take.crc32c == base64.b64encode(expected.digest()).decode("ascii")
    assert take.sha256 in take.storage_key
    assert take.size_bytes == len(AUDIO)


@pytest.mark.asyncio
async def test_the_same_take_sent_twice_is_stored_once(db_session: AsyncSession):
    store = MemoryStore()

    first = await _keep(db_session, store)
    second = await _keep(db_session, store)

    assert second.id == first.id
    assert store.writes == 1, "a chave é o hash do áudio — reenviar não pode duplicar nada"


@pytest.mark.asyncio
async def test_a_different_take_gets_its_own_object(db_session: AsyncSession):
    store = MemoryStore()

    first = await _keep(db_session, store)
    second = await _keep(db_session, store, audio=b"a equipe contou de outro jeito")

    assert second.storage_key != first.storage_key
    assert len(store.objects) == 2


@pytest.mark.asyncio
async def test_a_bucket_that_refused_leaves_no_row_claiming_the_audio_is_safe(
    db_session: AsyncSession,
):
    with pytest.raises(RuntimeError):
        await _keep(db_session, RefusingStore())

    assert await service.takes_of(db_session, "sessao-1") == [], (
        "uma linha apontando para um objeto que nunca foi escrito é uma tomada "
        "que o app acha que está salva e ninguém consegue tocar"
    )


@pytest.mark.asyncio
async def test_an_empty_take_is_refused(db_session: AsyncSession):
    with pytest.raises(ValidationError):
        await _keep(db_session, MemoryStore(), audio=b"")


@pytest.mark.asyncio
async def test_an_oversized_take_is_refused_before_anything_is_stored(db_session: AsyncSession):
    store = MemoryStore()

    with pytest.raises(ValidationError):
        await _keep(db_session, store, audio=b"x" * (service.MAX_TAKE_BYTES + 1))

    assert store.objects == {}


@pytest.mark.asyncio
async def test_a_retro_chunk_carries_its_pass_and_position(db_session: AsyncSession):
    store = MemoryStore()

    take = await service.store_take(
        db_session,
        session_id="sessao-1",
        device_id=DEVICE,
        pericope="P03",
        kind=IRTakeKind.RETRO,
        scope="P03",
        audio=b"trecho contado de volta",
        pass_number=2,
        chunk_index=3,
        store=store,
    )

    assert (take.kind, take.pass_number, take.chunk_index) == (IRTakeKind.RETRO, 2, 3)
    assert "/retro/" in take.storage_key


@pytest.mark.asyncio
async def test_the_device_is_recorded_and_the_team_seat_is_left_open(db_session: AsyncSession):
    take = await _keep(db_session, MemoryStore())

    assert take.device_id == DEVICE
    assert take.team_id is None, (
        "a atribuição por aparelho é provisória — a coluna existe para o login "
        "de equipe reivindicar a linha depois, sem reescrita"
    )
