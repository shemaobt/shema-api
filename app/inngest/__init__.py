from app.inngest.audio_cleaning import clean_recording_fn
from app.inngest.audio_splitting import split_recording_fn
from app.inngest.sn_transcription import transcribe_session_answers_fn
from app.inngest.upload_processing import (
    fail_stalled_uploads_fn,
    process_upload_fn,
    purge_failed_uploads_fn,
)

ALL_FUNCTIONS = [
    process_upload_fn,
    fail_stalled_uploads_fn,
    purge_failed_uploads_fn,
    clean_recording_fn,
    split_recording_fn,
    transcribe_session_answers_fn,
]

__all__ = [
    "ALL_FUNCTIONS",
    "clean_recording_fn",
    "fail_stalled_uploads_fn",
    "process_upload_fn",
    "purge_failed_uploads_fn",
    "split_recording_fn",
    "transcribe_session_answers_fn",
]
