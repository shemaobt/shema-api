from pydantic import BaseModel, Field

#: The longest Sound Necklace question is ~200 characters; same ceiling as project_health.
MAX_TTS_CHARS = 3000


class TtsSpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TTS_CHARS)
    #: BCP-47 locale (`pt-BR`, `en-US`) — the locale->voice map lives in
    #: `services/platform/voices.py`.
    language: str = Field(min_length=2, max_length=16)


class SttTranscribeResponse(BaseModel):
    """What one recording said. A draft: no caller is told it is correct."""

    text: str
