from typing import Annotated

from fastapi import APIRouter, Query

from app.api.internalization_room._deps import room_caller_dep
from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.models.internalization_room import FixedLineView
from app.services import internalization_room as room
from app.services.internalization_room.fail_safe import her_line
from app.services.internalization_room.voice_handles import clip_url

router = APIRouter()


@router.get(
    "/fixed-lines/{line}",
    response_model=FixedLineView,
    dependencies=[room_caller_dep],
)
async def fixed_line(line: str, language: Annotated[str, Query(max_length=8)]) -> FixedLineView:
    text = her_line(line, language)
    if text is None:
        raise NotFoundError(f"No line {line!r} is voiced from her file")
    settings = get_settings()
    voiced, _ = await room.synthesize_facilitator_speech(text, language=language, settings=settings)
    return FixedLineView(audio_url=clip_url(voiced.key))
