from __future__ import annotations

import logging

from app.core.config import Settings
from app.core.exceptions import ValidationError
from app.services.translation_helper.transcribe_audio import transcribe_audio

logger = logging.getLogger(__name__)


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
