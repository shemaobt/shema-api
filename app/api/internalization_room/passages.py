import asyncio

from fastapi import APIRouter

from app.api.internalization_room._deps import room_caller_dep
from app.core.config import get_settings
from app.models.internalization_room import BookPassagesResponse, PassageView
from app.services import internalization_room as room
from app.services.internalization_room.canon.parse_map import load_book
from app.services.internalization_room.passage_lines import line_for
from app.services.internalization_room.voice_handles import clip_url

router = APIRouter()

#: Small on purpose: the synthesiser bills per call and rate-limits per key.
_VOICES_AT_ONCE = 4


@router.get(
    "/books/{book}/passages",
    response_model=BookPassagesResponse,
    dependencies=[room_caller_dep],
)
async def passages(book: str) -> BookPassagesResponse:
    """The passages of a book, each with the line the room says to name it out loud.

    A team that cannot read tells the passages apart by ear, so a passage nobody has written
    a line for is left out rather than offered as a number: the room would have nothing to
    say when the team touched it.

    The lines are synthesized through the same cache as every other spoken line, which is
    content-addressed — a book is paid for once and then answers every replica and deploy.
    """
    settings = get_settings()
    language = settings.internalization_room_language_code
    named = [
        (meaning_map.pericope_num, line)
        for meaning_map in load_book(book)
        for line in [line_for(meaning_map.pericope_num, language)]
        if line
    ]

    # In parallel, bounded. Fourteen passages meant fourteen round trips in a row inside
    # the app's ninety-second budget, and a cache cold for any reason — a new book, a
    # tuning change, which is part of the cache key — put the route over it. The room then
    # told a team on a working network that the internet was gone, while the server was
    # still working. The bound is there because the voice on the other end has a quota.
    gate = asyncio.Semaphore(_VOICES_AT_ONCE)

    async def voiced(line: str) -> str:
        async with gate:
            entry, _ = await room.synthesize_facilitator_speech(line, settings=settings)
            return clip_url(entry.key)

    urls = await asyncio.gather(*(voiced(line) for _, line in named))
    return BookPassagesResponse(
        book=book,
        passages=[
            PassageView(pericope=pericope, audio_url=url)
            for (pericope, _), url in zip(named, urls, strict=True)
        ],
    )
