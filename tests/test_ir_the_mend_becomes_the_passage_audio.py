"""The encoder behind the **Rebuild**, which nothing in the room calls any more.

The room used to answer a `replace` carrying no audio as a fragment of the rehearsal recorded
again: it kept the fragment as a recording of its own and assembled a new passage around it, so
that the corrected minute and everything around it were one file somebody could play. ADR 0025
removed the gesture — what a team re-records is the unit they rehearsed, and the recording
reaching Refine is the team's own — so the door this module drove through is gone, and the
cases that drove through it went with it (ENG-849).

What is left is the encoder itself, with no caller: `compose_passage` still has to produce
audio that decodes and lasts what the arithmetic says. It is kept until ENG-856 deletes the
module, so that the deletion is a deletion and not a silent regression in between.
"""

from __future__ import annotations

import importlib
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="needs ffmpeg and ffprobe on the PATH",
)
async def test_the_rebuilt_passage_is_audio_somebody_can_play() -> None:
    """The one case with a real encoder: what comes out has to be playable audio.

    Three tones make a passage of seven seconds; the middle three seconds are replaced by a
    tone of four. The result has to *decode*, and to last eight seconds — the passage grew by
    exactly the second the correction added. Tolerance because the encoder pads its last frame,
    not because the arithmetic is uncertain.
    """
    compose_module = importlib.import_module("app.services.internalization_room.compose")

    with tempfile.TemporaryDirectory() as workspace:
        room = Path(workspace)
        passage = _tones(room, [(440, 2), (660, 3), (880, 2)])
        correction = _tones(room, [(330, 4)])

        rebuilt = await compose_module.compose_passage(
            passage, correction, starts_ms=2000, ends_ms=5000
        )

        played = room / "refeita.m4a"
        played.write_bytes(rebuilt)
        assert abs(_seconds(played) - 8.0) < 0.1
        assert _codec(played) == "aac"

        opening = await compose_module.compose_passage(
            passage, correction, starts_ms=0, ends_ms=2000
        )
        first = room / "refeita-do-comeco.m4a"
        first.write_bytes(opening)
        assert abs(_seconds(first) - 9.0) < 0.1, (
            "corrigir o primeiro trecho deixa a cabeça vazia, e o encoder aceita"
        )

        trimmed = await compose_module.compose_passage(
            passage,
            correction,
            starts_ms=2000,
            ends_ms=5000,
            corrected_starts_ms=500,
            corrected_ends_ms=3500,
        )
        aparada = room / "refeita-com-fatia.m4a"
        aparada.write_bytes(trimmed)
        assert abs(_seconds(aparada) - 7.0) < 0.1, (
            "entra a fatia endereçada da correção, e não o arquivo em que ela está"
        )


def _tones(room: Path, parts: list[tuple[int, int]]) -> bytes:
    """One recording made of tones, as bytes — a passage, or one stretch of one."""
    pieces = []
    for index, (hertz, seconds) in enumerate(parts):
        piece = room / f"tom-{hertz}-{index}.wav"
        _ffmpeg(
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency={hertz}:duration={seconds}:sample_rate=44100",
            "-ac",
            "1",
            str(piece),
        )
        pieces.append(piece)

    listing = room / f"lista-{len(parts)}-{parts[0][0]}.txt"
    listing.write_text("".join(f"file '{piece}'\n" for piece in pieces))
    whole = room / f"inteiro-{parts[0][0]}.wav"
    _ffmpeg("-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(whole))
    return whole.read_bytes()


def _ffmpeg(*arguments: str) -> None:
    done = subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", *arguments], capture_output=True, timeout=120
    )
    assert done.returncode == 0, done.stderr.decode()


def _probe(path: Path, entries: str) -> str:
    done = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", entries, "-of", "csv=p=0", str(path)],
        capture_output=True,
        timeout=120,
    )
    assert done.returncode == 0, done.stderr.decode()
    return done.stdout.decode().strip()


def _seconds(path: Path) -> float:
    return float(_probe(path, "format=duration").splitlines()[0])


def _codec(path: Path) -> str:
    return _probe(path, "stream=codec_name").splitlines()[0]
