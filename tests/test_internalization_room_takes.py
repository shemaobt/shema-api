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
from app.services.platform.storage import StoredObject

DEVICE = "tablet-da-equipe-1"
AUDIO = b"a equipe contou a passagem inteira"


def _crc(data: bytes) -> str:
    checksum = Checksum()
    checksum.update(data)
    return base64.b64encode(checksum.digest()).decode("ascii")


class MemoryStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.writes = 0

    async def get(self, key: str) -> bytes | None:
        return self.objects.get(key)

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.writes += 1
        self.objects[key] = data

    async def stat(self, key: str) -> StoredObject | None:
        stored = self.objects.get(key)
        if stored is None:
            return None
        return StoredObject(size=len(stored), crc32c=_crc(stored))


class TruncatingStore(MemoryStore):
    """A bucket that accepted the write and kept less than it was given."""

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        await super().put(key, data[:-1], content_type)


class ForgetfulStore(MemoryStore):
    """A bucket that answered the write and has nothing under the key."""

    async def stat(self, key: str) -> StoredObject | None:
        return None


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

    assert take.crc32c == _crc(AUDIO)
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
async def test_the_device_is_recorded_and_the_project_comes_from_the_session(
    db_session: AsyncSession,
):
    take = await _keep(db_session, MemoryStore())

    assert take.device_id == DEVICE
    assert take.project_id is None, (
        "o take herda o projeto da sessão, e esta nomeia uma sessão que não existe — "
        "não há o que herdar. É o mesmo estado de uma sala cujo aparelho ainda não foi "
        "reivindicado, que ENG-440 aceita com projeto nulo em vez de recusar"
    )


@pytest.mark.asyncio
async def test_a_take_read_back_whole_is_marked_verified(db_session: AsyncSession):
    take = await _keep(db_session, MemoryStore())

    assert take.verified_at is not None


@pytest.mark.asyncio
async def test_a_bucket_that_kept_less_than_it_was_given_is_not_verified(
    db_session: AsyncSession,
):
    take = await _keep(db_session, TruncatingStore())

    assert take.verified_at is None, (
        "o checksum calculado na memória não prova nada sobre o objeto — quem prova é a releitura"
    )


@pytest.mark.asyncio
async def test_a_bucket_with_nothing_under_the_key_is_not_verified(db_session: AsyncSession):
    take = await _keep(db_session, ForgetfulStore())

    assert take.verified_at is None


@pytest.mark.asyncio
async def test_an_unverified_take_is_still_recorded(db_session: AsyncSession):
    await _keep(db_session, TruncatingStore())

    assert await service.takes_of(db_session, "sessao-1") != [], (
        "recusar faria o app reenviar os mesmos bytes para a mesma chave e "
        "reproduzir o mesmo problema — uma linha sem verificação é algo que "
        "alguém pode ir olhar, uma tomada perdida não"
    )


@pytest.mark.asyncio
async def test_two_different_stretches_of_identical_audio_become_one_take(
    db_session: AsyncSession,
):
    """The trap the next person will step on, written down as a case rather than as a comment.

    Deduplication is by the hash of the bytes and the session, and the key carries neither the
    scope nor the position — so two *different* stretches that happen to hold byte-identical
    audio collapse into the first one's row, silently, and the second one comes back wearing
    the first one's position.

    This is why a stretch cannot be a take. It is measured here rather than argued: a segment
    is a row that points at a take, so two segments over one recording are two rows and the
    collapse costs nothing; a design where each stretch owned a file would lose the second one
    the moment the audio repeated.
    """
    store = MemoryStore()

    def _stretch(chunk_index: int):
        return service.store_take(
            db_session,
            session_id="sessao-1",
            device_id=DEVICE,
            pericope="P03",
            kind=IRTakeKind.RETRO,
            scope="P03",
            audio=b"os mesmos bytes exatos",
            chunk_index=chunk_index,
            store=store,
        )

    first = await _stretch(1)
    second = await _stretch(2)

    assert second.id == first.id
    assert second.chunk_index == 1, "o segundo volta com a posição do primeiro, sem avisar"
    assert len(store.objects) == 1
