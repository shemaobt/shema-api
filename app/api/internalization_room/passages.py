import asyncio
import logging
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room._deps import device_project_dep, linked_tablet_dep
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.exceptions import UpstreamServiceError, ValidationError
from app.models.internalization_room import (
    BookPassagesResponse,
    PassageView,
    ServedBooksResponse,
)
from app.services import internalization_room as room
from app.services.internalization_room.approved_draft import standing_approvals
from app.services.internalization_room.canon.elements import absence_index, element_keys
from app.services.internalization_room.canon.parse_map import load_map, served_books
from app.services.internalization_room.coverage import PANORAMA_PREFIX
from app.services.internalization_room.languages import floor, normalize
from app.services.internalization_room.passage_lines import offered, panorama_line_for
from app.services.internalization_room.voice_handles import clip_url

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_LINES_IN_FLIGHT = 4


async def _voiced(
    entry: str, line: str, *, language: str, settings: Settings, in_flight: asyncio.Semaphore
) -> str | None:
    """One entry's line, synthesized while at most a few others are in flight, or None when
    no line is written or the voice provider fails or refuses that line (unreachable, 5xx,
    quota, a 4xx for it): the list is served either way (ADR 0066). A missing key is ours and
    not the provider's (`ProviderNotConfigured`), and fails the list, as any other defect of
    ours does."""
    if not line:
        return None
    async with in_flight:
        try:
            voiced, _ = await room.synthesize_facilitator_speech(
                line, language=language, settings=settings
            )
        except (UpstreamServiceError, ValidationError, httpx.HTTPError):
            logger.warning("%s could not be voiced in %s", entry, language, exc_info=True)
            return None
        except Exception:
            logger.exception("%s hit a defect on our side while voiced in %s", entry, language)
            raise
    return clip_url(voiced.key)


async def _passage(
    pericope_num: str,
    line: str,
    *,
    language: str,
    approved: bool,
    settings: Settings,
    in_flight: asyncio.Semaphore,
) -> PassageView:
    return PassageView(
        pericope=pericope_num,
        kind="passage",
        audio_url=await _voiced(
            pericope_num, line, language=language, settings=settings, in_flight=in_flight
        ),
        reference=load_map(pericope_num).reference,
        beads=len(element_keys(pericope_num)),
        absence_index=absence_index(pericope_num),
        approved=approved,
    )


async def _panorama(
    book: str, *, language: str, settings: Settings, in_flight: asyncio.Semaphore
) -> PassageView:
    """The book's own entry, under the id the open door takes.

    No beads and no absence index: the panorama holds no elements of its own, so both stay
    at the defaults a passage without either already carries.
    """
    panorama = PANORAMA_PREFIX + book
    return PassageView(
        pericope=panorama,
        kind="panorama",
        audio_url=await _voiced(
            panorama,
            panorama_line_for(book, language),
            language=language,
            settings=settings,
            in_flight=in_flight,
        ),
    )


@router.get("/books", response_model=ServedBooksResponse, dependencies=[linked_tablet_dep])
async def books() -> ServedBooksResponse:
    """The books the room serves, in the order of their passage ids."""
    return ServedBooksResponse(books=served_books())


@router.get(
    "/books/{book}/passages",
    response_model=BookPassagesResponse,
    dependencies=[linked_tablet_dep],
)
async def passages(
    book: str,
    language: Annotated[str | None, Query(max_length=8)] = None,
    project_id: str = device_project_dep,
    db: AsyncSession = Depends(get_db),
) -> BookPassagesResponse:
    """The book's Panorama, then every passage of the book in story order, each with the line
    the room says to name it out loud (ADR 0066).

    The lines are synthesized through the same cache as every other spoken line, which is
    content-addressed — a book is paid for once and then answers every replica and deploy.

    This is the one room route that negotiates a language of its own. Every other spoken
    thing rides a session, which names its language once at the open so the room cannot change
    language underneath a team mid-passage — but the wheel is what a team turns *before* there
    is a session, so there is no row to read the choice from and it has to be asked for here.

    The lines are voiced together rather than one after the other. This is the wheel the
    team turns before choosing where to work, so its wait is the first thing they meet, and
    a wheel that takes a round trip per entry end to end reads to them as no internet — a
    bucket read each when the cache is warm, a whole ElevenLabs call each when it is cold,
    which a new book or a change to the voice tuning both make it. A few at a time rather
    than all of them, because the room's ElevenLabs key carries its own quota and a cold
    book should not spend it in one breath. Story order is the order they come back in.

    Each passage says whether the team's draft of it stands approved (`approved`, ADR 0081),
    read once for the whole book from the caller's team; the panorama is never approved.
    """
    settings = get_settings()
    spoken = floor(settings) if language is None else normalize(language)
    if spoken is None:
        raise ValidationError(f"The room does not speak {language!r}")
    team_approved = await standing_approvals(db, project_id)
    await db.commit()
    in_flight = asyncio.Semaphore(MAX_LINES_IN_FLIGHT)
    every_passage = offered(book, spoken)
    said = await asyncio.gather(
        _panorama(book, language=spoken, settings=settings, in_flight=in_flight),
        *(
            _passage(
                pericope_num,
                line,
                language=spoken,
                approved=pericope_num in team_approved,
                settings=settings,
                in_flight=in_flight,
            )
            for pericope_num, line in every_passage
        ),
    )
    return BookPassagesResponse(book=book, passages=list(said))
