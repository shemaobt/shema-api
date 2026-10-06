from __future__ import annotations

import logging
import re

from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings
from app.core.exceptions import ValidationError
from app.services.internalization_room.languages import FLOOR
from app.services.platform.audio_duration import measure_ms
from app.services.translation_helper.transcribe_audio import (
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


#: Her `LONG_WORDLESS_TAKE_MS`: a take with no words that runs this long is the team
#: rehearsing in a language the transcriber cannot write, not a take the room missed.
LONG_WORDLESS_TAKE_MS = 20_000


def _mother_tongue_floor() -> float:
    return get_settings().internalization_room_mother_tongue_floor


class HeardSpeech(BaseModel):
    """A transcript plus the trusted transport facts the comprehension flow reads.

    ``mother_tongue`` is her `decideTeamUtterance`, three conditions and nothing else:
    another language heard, the session's own language heard under the mother-tongue floor,
    or a take with no words lasting twenty seconds or more. The session's language is what
    ``bridge_language`` carries; it used to be "not Portuguese", and a room speaking any
    other language met every utterance with the off-bridge fail-safe.

    It used to need a 0.98 detection and three words besides, so a Terena take the
    transcriber wrote out as Spanish at 0.7 reached the Guide as Spanish, and two minutes of
    rehearsal with no words were answered with a request to repeat. Her rule has no
    probability bar on another language: a language the room does not speak is never the
    team's answer, whatever the transcriber's confidence. Nor does the room second-guess
    words in the session's language by their word-level confidence any more: an unsure
    transcript of clear Portuguese is still the team's answer, and asking them to repeat it
    was the room failing them. A missing code never makes a take the mother tongue, nor does
    a missing probability for the session's own language — that is a transcriber that said
    nothing, not one that heard another language.

    ``measured_ms`` is the length as the take was measured, which the twenty seconds are
    read against, so a take of 19.6 s is a miss even though it is said as twenty.
    ``take_ms`` is the length as the note says it and the record keeps it: whole seconds for
    a measured take, and the Golden door's own seconds as her script gives them.
    ``mother_tongue_floor`` is the one the take was heard against, read from the deployment
    on every take and never kept on the session.
    """

    text: str = ""
    bridge_language: str = FLOOR
    language_code: str | None = None
    language_probability: float | None = None
    take_ms: float | None = None
    measured_ms: float | None = None
    mother_tongue_floor: float = Field(default_factory=_mother_tongue_floor)
    #: The team cut the Guide's previous reply short to say this.
    interrupted: bool = False

    @property
    def mother_tongue(self) -> bool:
        if not self.text.strip():
            return self.measured_ms is not None and self.measured_ms >= LONG_WORDLESS_TAKE_MS
        detected = (self.language_code or "").strip().lower().split("-")[0]
        if not detected:
            return False
        spoken = _BRIDGE_LANGUAGE_CODES.get(self.bridge_language, _BRIDGE_LANGUAGE_CODES[FLOOR])
        if detected not in spoken:
            return True
        heard = self.language_probability
        return heard is not None and heard < self.mother_tongue_floor


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

    Every take is measured, the one the transcriber refuses as empty included: a take with no
    words is told apart from a long rehearsal only by its length, and the record keeps the
    length of every turn.
    """
    mother_tongue_floor = (settings or get_settings()).internalization_room_mother_tongue_floor
    try:
        result = await transcribe_audio_detailed(
            audio, filename=filename, mime_type=mime_type, settings=settings
        )
    except ValidationError as failure:
        logger.info("Nothing made out of %d bytes of audio: %s", len(audio), failure)
        result = TranscriptionResult(text="")
    measured = await measure_ms(audio)
    return HeardSpeech(
        text=spoken_words_only(result.text),
        bridge_language=language,
        language_code=result.language_code,
        language_probability=result.language_probability,
        take_ms=None if measured is None else round(measured, -3),
        measured_ms=measured,
        mother_tongue_floor=mother_tongue_floor,
    )
