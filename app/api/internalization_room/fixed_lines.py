from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room._deps import linked_tablet_dep
from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import NotFoundError, ValidationError
from app.models.internalization_room import FixedLineView
from app.services import internalization_room as room
from app.services.internalization_room.fail_safe import her_line
from app.services.internalization_room.languages import normalize
from app.services.internalization_room.voice_handles import clip_url

router = APIRouter()


@router.get(
    "/fixed-lines/{line}",
    response_model=FixedLineView,
    dependencies=[linked_tablet_dep],
)
async def fixed_line(
    line: str,
    language: Annotated[str, Query(max_length=8)],
    db: AsyncSession = Depends(get_db),
) -> FixedLineView:
    spoken = normalize(language)
    if spoken is None:
        raise ValidationError(f"The room does not speak {language!r}")
    text = her_line(line, spoken)
    if text is None:
        raise NotFoundError(f"No line {line!r} is voiced from her file")
    await db.commit()
    settings = get_settings()
    voiced, _ = await room.synthesize_facilitator_speech(text, language=spoken, settings=settings)
    return FixedLineView(audio_url=clip_url(voiced.key))
