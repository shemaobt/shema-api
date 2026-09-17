"""How long a recording runs, read from the audio itself.

ffprobe rather than a Python container parser, because ffmpeg is already this repository's
answer to reading audio — `oral_collector/split_service.py` and `inngest/audio_splitting.py`
both shell out to it, and both `Dockerfile` and `Dockerfile.dev` install it. A second
mechanism for the same question is how two correct answers drift apart.

The container is recognised by its own bytes, so this is indifferent to the `content_type`
the caller declares. That matters on the question path, where every clip is stored as
`audio/mp4` regardless of what arrived (ENG-526): a measurement that trusted the label would
be wrong for exactly the recordings that bug mislabels.
"""

from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

PROBE = "ffprobe"


async def measure_ms(audio: bytes) -> int | None:
    """The recording's length in milliseconds, or ``None`` when it cannot be read.

    ``None`` covers three situations on purpose — the tool is not installed, the tool
    failed, or the bytes are not audio — because every caller so far does the same thing
    with all three: keep the recording and show it without a length. A raised hand that
    cannot be measured is still a raised hand, and refusing it would lose a team's question
    over a missing package on a machine.

    Written to a temporary file rather than piped in: a phone leaves the MP4 ``moov`` atom
    at the end of the file, and a probe reading a pipe cannot seek back to it.
    """
    if not audio:
        return None

    with tempfile.NamedTemporaryFile(suffix=".audio") as handle:
        handle.write(audio)
        handle.flush()
        seconds = await _probe_seconds(Path(handle.name))

    if seconds is None:
        return None
    return round(seconds * 1000)


async def _probe_seconds(path: Path) -> float | None:
    """Ask ffprobe for the container's own duration, in seconds.

    The boundary is here and only here: a missing binary, a non-zero exit and unreadable
    output are all this process meeting the outside world, and each is reported as "no
    measurement" rather than raised at a caller with nothing to do about it.
    """
    try:
        probe = await asyncio.create_subprocess_exec(
            PROBE,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except (FileNotFoundError, NotADirectoryError, PermissionError):
        logger.warning("%s is not installed: audio is stored without a duration", PROBE)
        return None

    stdout, stderr = await probe.communicate()
    if probe.returncode != 0:
        logger.warning("%s could not read the audio: %s", PROBE, stderr.decode()[:200])
        return None

    try:
        return float(stdout.decode().strip())
    except ValueError:
        logger.warning("%s reported no duration for this audio", PROBE)
        return None
