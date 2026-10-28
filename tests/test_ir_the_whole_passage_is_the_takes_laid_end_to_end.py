"""The whole passage is the live takes' samples laid end to end under one header.

Her whole-passage download (app/api/draft/export/whole/route.ts): nothing is re-encoded and
nothing is reordered, so what Refine receives is what the team approved.
"""

from __future__ import annotations

import hashlib
import io
import wave
from array import array

import pytest

from app.core.exceptions import NotAllWav
from app.db.models.internalization_room import IRTake, IRTakeKind
from app.services.internalization_room.whole_passage import whole_passage
from tests.hard_stretch_harness import MemoryStore

RATE = 16000
RELEASE = "terena-P01-v1"


def _wav(samples: list[int], rate: int = RATE, channels: int = 1, width: int = 2) -> bytes:
    out = io.BytesIO()
    with wave.open(out, "wb") as file:
        file.setnchannels(channels)
        file.setsampwidth(width)
        file.setframerate(rate)
        file.writeframes(array("h", samples).tobytes() if width == 2 else bytes(len(samples)))
    return out.getvalue()


def _format(wav: bytes) -> tuple[int, int, int]:
    with wave.open(io.BytesIO(wav), "rb") as file:
        return file.getframerate(), file.getnchannels(), file.getsampwidth()


def _samples(wav: bytes) -> list[int]:
    with wave.open(io.BytesIO(wav), "rb") as file:
        return list(array("h", file.readframes(file.getnframes())))


def _take(store: MemoryStore, audio: bytes, ordinal: int | None) -> IRTake:
    sha = hashlib.sha256(audio).hexdigest()
    key = f"internalization-room/takes/s/ensaio/{sha}/tomada.wav"
    store.objects[key] = audio
    return IRTake(kind=IRTakeKind.ENSAIO, ordinal=ordinal, sha256=sha, storage_key=key)


class CountingStore(MemoryStore):
    def __init__(self) -> None:
        super().__init__()
        self.puts: list[str] = []

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.puts.append(key)
        await super().put(key, data, content_type)


SCENES = [
    [(n * 7) % 3000 - 1500 for n in range(RATE)],
    [(n * 11) % 4000 - 2000 for n in range(RATE // 2)],
    [(n * 13) % 5000 - 2500 for n in range(RATE * 2)],
]


async def test_three_scene_takes_become_one_file_in_scene_order() -> None:
    store = MemoryStore()
    takes = [_take(store, _wav(scene), ordinal) for ordinal, scene in enumerate(SCENES, start=1)]

    key = await whole_passage(store, RELEASE, takes)

    assert _samples(store.objects[key]) == SCENES[0] + SCENES[1] + SCENES[2]
    assert _format(store.objects[key]) == (RATE, 1, 2)


async def test_a_passage_recorded_whole_is_its_one_take_unchanged() -> None:
    store = MemoryStore()
    take = _take(store, _wav(SCENES[2]), None)

    key = await whole_passage(store, RELEASE, [take])

    assert _samples(store.objects[key]) == SCENES[2]


async def test_the_same_takes_are_served_from_the_same_key_without_a_second_build() -> None:
    store = CountingStore()
    takes = [_take(store, _wav(scene), n) for n, scene in enumerate(SCENES, start=1)]
    first = await whole_passage(store, RELEASE, takes)
    built = len(store.puts)

    again = await whole_passage(store, RELEASE, takes)

    assert again == first
    assert len(store.puts) == built, "o arquivo foi refeito"


async def test_a_re_recorded_scene_makes_a_new_key_and_the_earlier_file_stays() -> None:
    store = MemoryStore()
    takes = [_take(store, _wav(scene), n) for n, scene in enumerate(SCENES, start=1)]
    before = await whole_passage(store, RELEASE, takes)
    takes[1] = _take(store, _wav(SCENES[0][:1000]), 2)

    after = await whole_passage(store, RELEASE, takes)

    assert after != before
    assert _samples(store.objects[after]) == SCENES[0] + SCENES[0][:1000] + SCENES[2]
    assert _samples(store.objects[before]) == SCENES[0] + SCENES[1] + SCENES[2]


async def test_a_new_version_of_the_release_makes_a_new_key() -> None:
    store = MemoryStore()
    takes = [_take(store, _wav(SCENES[0]), 1)]

    first = await whole_passage(store, "terena-P01-v1", takes)
    second = await whole_passage(store, "terena-P01-v2", takes)

    assert first != second
    assert _samples(store.objects[first]) == SCENES[0], "o arquivo da versão anterior se perdeu"
    assert first.startswith("internalization-room/whole/terena-P01-v1/")
    assert first.endswith(".wav")


@pytest.mark.parametrize(
    "stranger",
    [
        _wav(SCENES[0], rate=44100),
        _wav(SCENES[0] * 2, channels=2),
        _wav(SCENES[0], width=1),
        b"RIFFnot a wav at all",
    ],
    ids=["44.1 kHz", "stereo", "8-bit", "no header"],
)
async def test_a_take_whose_header_is_not_16khz_mono_16bit_refuses_the_whole(
    stranger: bytes,
) -> None:
    store = MemoryStore()
    takes = [_take(store, _wav(SCENES[0]), 1), _take(store, stranger, 2)]

    with pytest.raises(NotAllWav):
        await whole_passage(store, RELEASE, takes)

    assert not any(key.startswith("internalization-room/whole/") for key in store.objects)


async def test_a_take_the_bucket_no_longer_holds_refuses_the_whole() -> None:
    store = MemoryStore()
    takes = [_take(store, _wav(SCENES[0]), 1), _take(store, _wav(SCENES[1]), 2)]
    del store.objects[takes[1].storage_key]

    with pytest.raises(NotAllWav):
        await whole_passage(store, RELEASE, takes)
