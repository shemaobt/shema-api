"""The whole approved passage as one WAV: the live takes' samples laid end to end."""

from __future__ import annotations

import hashlib

from app.core.exceptions import NotAllWav
from app.db.models.internalization_room import IRTake
from app.services.internalization_room.takes import TakeStore
from app.services.internalization_room.wav import Pcm, pcm16

RATE = 16000
CHANNELS = 1


def whole_key(release_id: str, takes: list[IRTake]) -> str:
    """Deterministic in the release and the takes in order, so a changed take is a new file."""
    digest = hashlib.sha256("".join(take.sha256 for take in takes).encode()).hexdigest()
    return f"internalization-room/whole/{release_id}/{digest}.wav"


async def whole_passage(store: TakeStore, release_id: str, takes: list[IRTake]) -> str:
    """The key of the joined file, built only when the bucket does not hold it yet.

    The takes are laid in scene order, whatever order they come in. Every take's own header is
    read first, so a take the record calls WAV and the bytes do not, or that holds no sample,
    refuses the whole before anything is written.
    """
    if not takes:
        raise NotAllWav("the passage has no take to lay down")
    scenes = sorted(takes, key=lambda take: take.ordinal or 0)
    key = whole_key(release_id, scenes)
    if await store.stat(key) is None:
        data = b"".join([_samples(await store.get(take.storage_key)) for take in scenes])
        await store.put(key, Pcm(rate=RATE, channels=CHANNELS, data=data).wav(data), "audio/wav")
    return key


def _samples(recording: bytes | None) -> bytes:
    pcm = None if recording is None else pcm16(recording)
    if pcm is None or not pcm.data or pcm.rate != RATE or pcm.channels != CHANNELS:
        raise NotAllWav("a take of the passage is not 16 kHz mono 16-bit WAV")
    return pcm.data
