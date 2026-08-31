import asyncio
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.internalization_room._deps import room_caller_dep
from app.core.config import Settings, get_settings
from app.core.exceptions import ValidationError
from app.models.internalization_room import BookPassagesResponse, PassageView
from app.services import internalization_room as room
from app.services.internalization_room.canon.book_material import unwalkable
from app.services.internalization_room.canon.elements import absence_index, element_keys
from app.services.internalization_room.canon.parse_map import load_book
from app.services.internalization_room.languages import FLOOR, normalize
from app.services.internalization_room.passage_lines import line_for
from app.services.internalization_room.voice_handles import clip_url

router = APIRouter()

MAX_LINES_IN_FLIGHT = 4


async def _voiced(
    pericope_num: str,
    line: str,
    *,
    book: str,
    language: str,
    settings: Settings,
    in_flight: asyncio.Semaphore,
) -> PassageView:
    """One passage's line, synthesized while at most a few others are in flight."""
    async with in_flight:
        voiced, _ = await room.synthesize_facilitator_speech(
            line, language=language, settings=settings
        )
    return PassageView(
        pericope=pericope_num,
        audio_url=clip_url(voiced.key),
        beads=len(element_keys(pericope_num, book=book)),
        absence_index=absence_index(pericope_num, book=book),
    )


@router.get(
    "/books/{book}/passages",
    response_model=BookPassagesResponse,
    dependencies=[room_caller_dep],
)
async def passages(
    book: str,
    language: Annotated[str, Query(max_length=8)] = FLOOR,
) -> BookPassagesResponse:
    """The passages of a book, each with the line the room says to name it out loud.

    A team that cannot read tells the passages apart by ear, so a passage nobody has written
    a line for is left out rather than offered as a number: the room would have nothing to
    say when the team touched it.

    A passage the session would refuse is left out on the same grounds. The wheel is the only
    way in, and it offered all fourteen while `require_walkable` turned eight of them away —
    so a finger landing on one bought a refusal the app could only read as a broken room. A
    spoke that cannot be entered is worse than a spoke that was never offered.

    The lines are synthesized through the same cache as every other spoken line, which is
    content-addressed — a book is paid for once and then answers every replica and deploy.

    This is the one room route that negotiates a language of its own. Every other spoken
    thing rides a session, which names its language once at the open so the room cannot change
    language underneath a team mid-passage — but the wheel is what a team turns *before* there
    is a session, so there is no row to read the choice from and it has to be asked for here.

    The lines are voiced together rather than one after the other. This is the wheel the
    team turns before choosing where to work, so its wait is the first thing they meet, and
    a wheel that takes fourteen round trips end to end reads to them as no internet — a
    bucket read each when the cache is warm, a whole ElevenLabs call each when it is cold,
    which a new book or a change to the voice tuning both make it. A few at a time rather
    than all fourteen, because the room's ElevenLabs key carries its own quota and a cold
    book should not spend it in one breath. Story order is the order they come back in.
    """
    spoken = normalize(language)
    if spoken is None:
        raise ValidationError(f"The room does not speak {language!r}")
    settings = get_settings()
    in_flight = asyncio.Semaphore(MAX_LINES_IN_FLIGHT)
    speakable = [
        (meaning_map.pericope_num, line)
        for meaning_map in load_book(book)
        if not unwalkable(meaning_map) and (line := line_for(meaning_map.pericope_num, spoken))
    ]
    said = await asyncio.gather(
        *(
            _voiced(
                pericope_num,
                line,
                book=book,
                language=spoken,
                settings=settings,
                in_flight=in_flight,
            )
            for pericope_num, line in speakable
        )
    )
    return BookPassagesResponse(book=book, passages=list(said))
