"""The scheduling of the stalled-upload sweep and of the purge that drains what it leaves.

What each pass does is tested in `tests/test_oc_recording_service.py`, against a database.
What only the registration can say is that anything runs them at all: `UPLOADING` has no other
exit, so a sweep that is written but never served leaves the rows exactly as stuck as before,
and a purge nothing calls lets `UPLOAD_FAILED` accumulate as it does today.
"""

from __future__ import annotations

import pytest

pytest.importorskip("app.inngest")

from app.inngest import ALL_FUNCTIONS
from app.inngest.upload_processing import FAILED_UPLOAD_PURGE_CRON, STALLED_UPLOAD_SWEEP_CRON

FN_ID = "fail-stalled-uploads"
PURGE_FN_ID = "purge-failed-uploads"


def _config(fn_id: str = FN_ID):
    fn = next(f for f in ALL_FUNCTIONS if f.id.endswith(fn_id))
    return fn.get_config("http://test").main


def test_the_sweep_is_registered_to_be_served() -> None:
    assert any(f.id.endswith(FN_ID) for f in ALL_FUNCTIONS)


def test_the_sweep_runs_on_a_schedule_rather_than_on_an_event() -> None:
    assert [t.cron for t in _config().triggers] == [STALLED_UPLOAD_SWEEP_CRON]


def test_the_purge_is_registered_to_be_served() -> None:
    assert any(f.id.endswith(PURGE_FN_ID) for f in ALL_FUNCTIONS)


def test_the_purge_runs_on_a_schedule_rather_than_on_an_event() -> None:
    assert [t.cron for t in _config(PURGE_FN_ID).triggers] == [FAILED_UPLOAD_PURGE_CRON]
