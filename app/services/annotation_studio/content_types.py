from app.core.as_enums import AsAudioFormat

_MIME = {
    AsAudioFormat.WEBM: "audio/webm",
    AsAudioFormat.WAV: "audio/wav",
    AsAudioFormat.MP3: "audio/mpeg",
    AsAudioFormat.FLAC: "audio/flac",
}


def content_type_for_format(fmt: AsAudioFormat | str) -> str:
    return _MIME.get(AsAudioFormat(fmt), "application/octet-stream")
