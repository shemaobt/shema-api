"""The scheduling of the stalled-upload sweep.

What the sweep does is tested in `tests/test_oc_recording_service.py`, against a database.
What only the registration can say is that anything runs it at all: `UPLOADING` has no other
exit, so a sweep that is written but never served leaves the rows exactly as stuck as before.
"""

from __future__ import annotations

import pytest

pytest.importorskip("app.inngest")

from app.inngest import ALL_FUNCTIONS
from app.inngest.upload_processing import STALLED_UPLOAD_SWEEP_CRON

FN_ID = "fail-stalled-uploads"


def _config():
    fn = next(f for f in ALL_FUNCTIONS if f.id.endswith(FN_ID))
    return fn.get_config("http://test").main


def test_the_sweep_is_registered_to_be_served() -> None:
    assert any(f.id.endswith(FN_ID) for f in ALL_FUNCTIONS)


def test_the_sweep_runs_on_a_schedule_rather_than_on_an_event() -> None:
    assert [t.cron for t in _config().triggers] == [STALLED_UPLOAD_SWEEP_CRON]
