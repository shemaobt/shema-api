from fastapi import APIRouter

from app.api.internalization_room._deps import room_key_dep
from app.core.config import get_settings
from app.models.internalization_room import BookPassagesResponse, PassageView
from app.services import internalization_room as room
from app.services.internalization_room.canon.parse_map import load_book
from app.services.internalization_room.passage_lines import line_for
from app.services.internalization_room.voice_handles import clip_url

router = APIRouter()


@router.get(
    "/books/{book}/passages",
    response_model=BookPassagesResponse,
    dependencies=[room_key_dep],
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
    said = []
    for meaning_map in load_book(book):
        line = line_for(meaning_map.pericope_num, language)
        if not line:
            continue
        voiced, _ = await room.synthesize_facilitator_speech(line, settings=settings)
        said.append(
            PassageView(
                pericope=meaning_map.pericope_num,
                audio_url=clip_url(voiced.key),
            )
        )
    return BookPassagesResponse(book=book, passages=said)
