"""A re-recorded sentence is laid into its part on the bytes themselves.

Her splice (src/audio/wav.ts at 18fa7c4, docs/ENSAIO-FINAL-SPEC.md §6.4): the new sentence keeps
0.2 s of its silence on each side, and replaces the old one inside the part with the audio before
and after it byte for byte the same, which is what lets the listening to them stand.
"""

from __future__ import annotations

import io
import wave
from array import array

from app.services.internalization_room.wav import Pcm, pcm16, splice_sentence, trim_silence

RATE = 16000


def _wav(samples: list[int], rate: int = RATE) -> bytes:
    out = io.BytesIO()
    with wave.open(out, "wb") as file:
        file.setnchannels(1)
        file.setsampwidth(2)
        file.setframerate(rate)
        file.writeframes(array("h", samples).tobytes())
    return out.getvalue()


def _samples(wav: bytes) -> list[int]:
    with wave.open(io.BytesIO(wav), "rb") as file:
        return list(array("h", file.readframes(file.getnframes())))


def _pcm(wav: bytes) -> Pcm:
    pcm = pcm16(wav)
    assert pcm is not None
    return pcm


def _seconds(count: float, value: int) -> list[int]:
    return [value] * int(count * RATE)


def test_a_sentence_keeps_a_fifth_of_a_second_of_silence_on_each_side() -> None:
    recorded = _wav(_seconds(0.5, 0) + _seconds(1.0, 9000) + _seconds(0.7, 0))

    kept = list(array("h", trim_silence(_pcm(recorded)).data))

    assert len(kept) == int(1.4 * RATE), "a frase entrava com todo o silêncio que foi gravado"
    assert kept[: int(0.2 * RATE)] == [0] * int(0.2 * RATE)
    assert kept[int(0.2 * RATE) : int(1.2 * RATE)] == [9000] * RATE


def test_the_audio_before_and_after_the_sentence_is_the_same_byte_for_byte() -> None:
    before, old, after = (
        [(n * 7) % 3000 - 1500 for n in range(RATE)],
        _seconds(1.0, 500),
        [(n * 11) % 4000 - 2000 for n in range(RATE)],
    )
    sentence = _wav(_seconds(0.3, 0) + _seconds(1.0, 9000) + _seconds(0.3, 0))

    spliced = splice_sentence(
        _pcm(_wav(before + old + after)), 1000, 2000, trim_silence(_pcm(sentence))
    )
    laid = _samples(spliced.audio)

    assert laid[:RATE] == before, "o áudio antes da frase mudava com a emenda"
    assert laid[-RATE:] == after, "o áudio depois da frase mudava com a emenda"
    assert len(laid) == int(3.4 * RATE)
    assert spliced.ends_ms == 2400, "a frase nova não terminava onde a emenda a pôs"
