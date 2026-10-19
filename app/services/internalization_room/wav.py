from __future__ import annotations

import struct
from array import array
from dataclasses import dataclass

KEPT_SILENCE_SECONDS = 0.2
SILENCE_FLOOR = 0.02
WINDOW_SECONDS = 0.01
FADE_SECONDS = 0.008


@dataclass(frozen=True)
class Pcm:
    rate: int
    channels: int
    data: bytes

    @property
    def block(self) -> int:
        return 2 * self.channels

    @property
    def frames(self) -> int:
        return len(self.data) // self.block

    def ms(self, frames: int) -> int:
        return round(frames * 1000 / self.rate)

    def frame_at(self, ms: int) -> int:
        return round(ms * self.rate / 1000)

    def wav(self, data: bytes) -> bytes:
        header = struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF",
            36 + len(data),
            b"WAVE",
            b"fmt ",
            16,
            1,
            self.channels,
            self.rate,
            self.rate * self.block,
            self.block,
            16,
            b"data",
            len(data),
        )
        return header + data


@dataclass(frozen=True)
class Spliced:
    audio: bytes
    ends_ms: int


def pcm16(wav: bytes) -> Pcm | None:
    if len(wav) < 12 or wav[:4] != b"RIFF" or wav[8:12] != b"WAVE":
        return None
    at, form = 12, None
    while at + 8 <= len(wav):
        name, size = wav[at : at + 4], struct.unpack("<I", wav[at + 4 : at + 8])[0]
        body = wav[at + 8 : at + 8 + size]
        if name == b"fmt " and len(body) >= 16:
            form = struct.unpack("<HHIIHH", body[:16])
        if name == b"data" and form is not None:
            kind, channels, rate, _, _, bits = form
            if kind != 1 or bits != 16 or not channels or not rate:
                return None
            return Pcm(
                rate=rate,
                channels=channels,
                data=body[: len(body) // (2 * channels) * 2 * channels],
            )
        at += 8 + size + size % 2
    return None


def trim_silence(pcm: Pcm) -> Pcm:
    samples = array("h", pcm.data)
    window = max(1, round(pcm.rate * WINDOW_SECONDS))
    loud = SILENCE_FLOOR * 0x8000
    heard = [
        start
        for start in range(0, pcm.frames, window)
        if max(map(abs, samples[start * pcm.channels : (start + window) * pcm.channels])) > loud
    ]
    if not heard:
        return pcm
    keep = round(KEPT_SILENCE_SECONDS * pcm.rate)
    first = max(0, heard[0] - keep)
    last = min(pcm.frames, heard[-1] + window + keep)
    return Pcm(
        rate=pcm.rate, channels=pcm.channels, data=pcm.data[first * pcm.block : last * pcm.block]
    )


def splice_sentence(part: Pcm, starts_ms: int, ends_ms: int, laid: Pcm) -> Spliced:
    first = part.frame_at(starts_ms)
    last = min(part.frames, part.frame_at(ends_ms))
    inserted = _faded(laid)
    return Spliced(
        audio=part.wav(part.data[: first * part.block] + inserted + part.data[last * part.block :]),
        ends_ms=part.ms(first + laid.frames),
    )


def _faded(pcm: Pcm) -> bytes:
    samples = array("h", pcm.data)
    fade = round(FADE_SECONDS * pcm.rate)
    if fade and pcm.frames >= 2 * fade:
        for frame in range(fade):
            for channel in range(pcm.channels):
                for at in (frame, pcm.frames - 1 - frame):
                    index = at * pcm.channels + channel
                    samples[index] = round(samples[index] * frame / fade)
    return samples.tobytes()
