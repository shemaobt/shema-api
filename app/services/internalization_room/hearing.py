from __future__ import annotations

import logging
import re

from pydantic import BaseModel

from app.core.config import Settings, get_settings
from app.core.exceptions import ValidationError
from app.services.internalization_room.languages import FLOOR
from app.services.platform.audio_duration import measure_ms
from app.services.translation_helper.transcribe_audio import (
    EmptyTranscription,
    TranscriptionResult,
    transcribe_audio,
    transcribe_audio_detailed,
)

logger = logging.getLogger(__name__)

_BRIDGE_LANGUAGE_CODES = {
    "pt": {"pt", "por"},
    "en": {"en", "eng"},
    "es": {"es", "spa"},
}

LONG_WORDLESS_TAKE_MS = 20_000

_BRACKETED = re.compile(r"\[[^\]]{0,60}\]|[♪♫]")
_ONLY_PARENTHETICAL = re.compile(r"^\s*\([^)]{0,60}\)\s*$")


def spoken_words_only(text: str) -> str:
    """The transcript minus what the transcriber wrote *about* the audio.

    A room with a fan, a passing truck or a moment of quiet comes back as
    ``[background music]``, ``[inaudible]`` or ``(silence)`` — the transcriber describing
    what it heard, not words anyone said. Handed on as speech it becomes a team utterance
    the Guide has to answer, and answering a stage direction produces a turn the Validator
    throws out, so the room says a canned line to a team that never spoke. Emptied here, it
    takes the path written for exactly this: the room says it could not make it out.

    Square brackets go wherever they stand, which is the convention every transcriber uses
    for this. Round brackets are only ever an annotation when they are the whole transcript
    — inside a sentence they are far likelier to be someone actually speaking.
    """
    if _ONLY_PARENTHETICAL.match(text):
        return ""
    return re.sub(r"\s{2,}", " ", _BRACKETED.sub(" ", text)).strip()


class HeardSpeech(BaseModel):
    """A transcript plus the transport facts that decide whether it reaches the Guide as words.

    ``mother_tongue`` is her ``decideTeamUtterance`` (``src/audio/teamUtterance.ts`` at
    a3f3c69): words the recognizer heard in a language other than the one *this session* is
    run in, which is what ``bridge_language`` carries, or in the session's own language with a
    probability under ``internalization_room_same_language_min_prob``; or a take with no words
    at all that lasted ``LONG_WORDLESS_TAKE_MS`` or more. A session language the room does not
    know is never "other".
    """

    text: str = ""
    bridge_language: str = FLOOR
    language_code: str | None = None
    language_probability: float | None = None
    take_ms: int | None = None
    wordless_long_take: bool = False
    declared_mother_tongue: bool = False

    @property
    def mother_tongue(self) -> bool:
        if self.wordless_long_take or self.declared_mother_tongue:
            return True
        detected = (self.language_code or "").strip().lower().split("-")[0]
        spoken = _BRIDGE_LANGUAGE_CODES.get(self.bridge_language)
        if not self.text.strip() or not detected or spoken is None:
            return False
        if detected not in spoken:
            return True
        return (
            self.language_probability is not None
            and self.language_probability
            < get_settings().internalization_room_same_language_min_prob
        )


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
        return spoken_words_only(
            await transcribe_audio(audio, filename=filename, mime_type=mime_type, settings=settings)
        )
    except ValidationError as failure:
        logger.info("Nothing made out of %d bytes of audio: %s", len(audio), failure)
        return ""


async def heard_speech(
    audio: bytes,
    *,
    filename: str | None = None,
    mime_type: str | None = None,
    language: str = FLOOR,
    settings: Settings | None = None,
) -> HeardSpeech:
    """`heard`, keeping the provider metadata the comprehension flow needs.

    ``language`` is the session's, and it is only ever the yardstick: the transcriber is
    still left to detect what it actually heard, because the whole point of the measurement
    is to notice a team that has slipped out of the language the room is speaking.
    """
    try:
        result = await transcribe_audio_detailed(
            audio, filename=filename, mime_type=mime_type, settings=settings
        )
    except EmptyTranscription:
        result = TranscriptionResult(text="")
    except ValidationError as failure:
        logger.info("Nothing made out of %d bytes of audio: %s", len(audio), failure)
        return HeardSpeech(bridge_language=language)
    speech = HeardSpeech(
        text=spoken_words_only(result.text),
        bridge_language=language,
        language_code=result.language_code,
        language_probability=result.language_probability,
    )
    if not speech.text:
        take_ms = await measure_ms(audio)
        if take_ms is not None and take_ms >= LONG_WORDLESS_TAKE_MS:
            speech.wordless_long_take = True
            speech.take_ms = take_ms
    elif speech.mother_tongue:
        speech.take_ms = await measure_ms(audio)
    return speech
