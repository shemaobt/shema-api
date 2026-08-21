from __future__ import annotations

import logging

from pydantic import BaseModel

from app.core.config import Settings
from app.core.exceptions import ValidationError
from app.services.translation_helper.transcribe_audio import (
    transcribe_audio,
    transcribe_audio_detailed,
)

logger = logging.getLogger(__name__)

_BRIDGE_LANGUAGE_CODES = {"pt", "por"}


class HeardSpeech(BaseModel):
    """A transcript plus the trusted transport facts the comprehension flow reads.

    ``mother_tongue`` intervenes only at a deliberately high threshold (0.98) and only on
    substantial speech, so an imperfect ordinary Portuguese detection cannot derail the
    conversation — and it is never a claim that the app understood the content.
    ``uncertain`` is used only to under-count: an uncertain transcript is repeated, never
    judged as misunderstanding; the threshold is lower for one- or two-word answers so a
    valid name in guided mode is not punished merely for being unfamiliar.
    """

    text: str = ""
    language_code: str | None = None
    language_probability: float | None = None
    transcript_confidence: float | None = None

    @property
    def mother_tongue(self) -> bool:
        words = self.text.split()
        substantial = len(words) >= 3 or len(self.text.strip()) >= 16
        detected = (self.language_code or "").strip().lower().split("-")[0]
        return bool(
            substantial
            and detected
            and detected not in _BRIDGE_LANGUAGE_CODES
            and self.language_probability is not None
            and self.language_probability >= 0.98
        )

    @property
    def uncertain(self) -> bool:
        if self.transcript_confidence is None:
            return False
        words = len(self.text.split())
        if not words:
            return False
        return self.transcript_confidence < (0.35 if words <= 2 else 0.55)

    @property
    def reliable_bridge_speech(self) -> bool:
        return not self.uncertain and not self.mother_tongue


async def heard(
    audio: bytes,
    *,
    filename: str | None = None,
    mime_type: str | None = None,
    settings: Settings | None = None,
) -> str:
    """What the team said, or an empty string when the room could not make it out.

    Not hearing someone is an ordinary moment in a room, not a client error. The transcriber
    raises for silence, for a clipped recording and for a file the encoder mangled — and a
    raise becomes a 4xx, which the app can only render as a network failure. The team is then
    told the internet is down because someone spoke too far from the microphone.

    Empty is the answer the turn already knows how to handle: it speaks the pre-approved
    *"não consegui ouvir direito — podem repetir?"*, which is why that line was written.
    """
    try:
        return await transcribe_audio(
            audio, filename=filename, mime_type=mime_type, settings=settings
        )
    except ValidationError as failure:
        logger.info("Nothing made out of %d bytes of audio: %s", len(audio), failure)
        return ""


async def heard_speech(
    audio: bytes,
    *,
    filename: str | None = None,
    mime_type: str | None = None,
    settings: Settings | None = None,
) -> HeardSpeech:
    """`heard`, keeping the provider metadata the comprehension flow needs."""
    try:
        result = await transcribe_audio_detailed(
            audio, filename=filename, mime_type=mime_type, settings=settings
        )
    except ValidationError as failure:
        logger.info("Nothing made out of %d bytes of audio: %s", len(audio), failure)
        return HeardSpeech()
    return HeardSpeech(
        text=result.text,
        language_code=result.language_code,
        language_probability=result.language_probability,
        transcript_confidence=result.transcript_confidence,
    )
