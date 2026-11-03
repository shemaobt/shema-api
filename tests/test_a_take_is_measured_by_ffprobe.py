from __future__ import annotations

from app.services.platform import audio_duration
from tests.scene_rehearsal_harness import recording


async def test_audio_duration_measures_a_short_real_file_with_ffprobe() -> None:
    measured = await audio_duration.measure_ms(recording(1, 7))

    assert measured is not None
    assert abs(measured - 1_000) <= 50
