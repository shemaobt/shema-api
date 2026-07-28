"""The queue wiring of the batch transcription (ENG-325).

The pass itself is tested in `tests/test_sound_necklace/test_transcriptions.py`, against a
database and with fake providers. What is checked here is what only the registration can
say: that the function the queue runs is the one the trigger sends to, and that two
triggers for one session cannot run at the same time — which is what keeps a double
trigger from paying the provider twice for the same answer.
"""

from __future__ import annotations

import pytest

pytest.importorskip("app.inngest")

from app.core.enums import SnTranscriptionEvent
from app.inngest import ALL_FUNCTIONS
from app.inngest.schemas import TranscriptionRequestedPayload

FN_ID = "transcribe-session-answers"


def _config():
    fn = next(f for f in ALL_FUNCTIONS if f.id.endswith(FN_ID))
    return fn.get_config("http://test").main


def test_the_function_is_registered_to_be_served() -> None:
    # Not in ALL_FUNCTIONS means not served, and the event would fall on the floor with the
    # trigger still answering 202.
    assert any(f.id.endswith(FN_ID) for f in ALL_FUNCTIONS)


def test_it_triggers_on_the_event_the_service_sends() -> None:
    assert [t.event for t in _config().triggers] == [SnTranscriptionEvent.REQUESTED.value]


def test_one_run_per_session_at_a_time() -> None:
    """Two runs over the same session would read the same pending rows and bill twice."""
    concurrency = _config().concurrency

    assert len(concurrency) == 1
    assert concurrency[0].key == "event.data.session_id"
    assert concurrency[0].limit == 1


def test_it_retries_because_a_dead_database_is_not_a_dead_job() -> None:
    # Per-answer failures are already recorded as `failed` rows by the pass itself; a
    # failure that reaches this level is infrastructure, and re-reading `pending` is safe.
    assert _config().steps["step"].retries.attempts == 3


def test_the_event_carries_the_session_and_nothing_else() -> None:
    # No snapshot of the work: the run reads whatever is pending when it starts, so a
    # replay never redoes a draft and never carries a stale one.
    assert set(TranscriptionRequestedPayload.model_fields) == {"session_id"}


def test_an_event_without_a_session_is_rejected() -> None:
    with pytest.raises(ValueError):
        TranscriptionRequestedPayload.model_validate({})
