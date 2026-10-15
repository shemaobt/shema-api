"""A scene rehearsal kept from the words of a golden script, with no recording behind it.

Her golden scripts carry a scene rehearsal as the frases the team translated. The tablet keeps
one from audio, through the recognizer and the bucket; here the words are given, so the same
writers keep the rehearsal and each frase over silence that is stored nowhere, under a device
no tablet can be called, with no check against a bucket ever made.
"""

from __future__ import annotations

import hashlib
import io
import wave

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSceneRehearsal, IRSession
from app.services.internalization_room import scene_rehearsals as scenes
from app.services.platform.storage import StoredObject

GOLDEN_DEVICE = "golden-runner"
FRASE_MS = 1000
WAV = "audio/wav"


class NoBucket:
    """A store that keeps nothing: what a golden rehearsal has in place of a recording."""

    async def get(self, key: str) -> bytes | None:
        return None

    async def put(self, key: str, data: bytes, content_type: str) -> bytes:
        return data

    async def stat(self, key: str) -> StoredObject | None:
        return None


def _silence(seconds: int, seed: str) -> bytes:
    """`seconds` of silence whose bytes follow `seed`, so no two golden recordings are one."""
    tone = int(hashlib.sha256(seed.encode()).hexdigest()[:6], 16) % 30_000
    out = io.BytesIO()
    with wave.open(out, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16_000)
        wav.writeframes(tone.to_bytes(2, "little") * 16_000 * seconds)
    return out.getvalue()


async def keep_a_golden_rehearsal(
    db: AsyncSession, session: IRSession, *, scene: str | None, pieces: list[str]
) -> IRSceneRehearsal:
    """The rehearsal and one frase for each piece with words, one second apart in her order."""
    spoken = [piece for piece in pieces if piece.strip()]
    store = NoBucket()
    rehearsal = await scenes.keep_scene_rehearsal(
        db,
        session,
        device_id=GOLDEN_DEVICE,
        audio=_silence(max(len(spoken), 1), f"{scene}|{'|'.join(spoken)}"),
        content_type=WAV,
        scene=scene,
        store=store,
    )
    for place, piece in enumerate(spoken):
        await scenes.keep_a_frase(
            db,
            session,
            rehearsal,
            starts_ms=place * FRASE_MS,
            ends_ms=(place + 1) * FRASE_MS,
            replaces=None,
            after_restart=None,
            audio=_silence(1, f"{scene}|{place}|{piece}"),
            content_type=WAV,
            filename=None,
            store=store,
            transcript=piece,
        )
    return rehearsal
