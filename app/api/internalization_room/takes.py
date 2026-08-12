"""The audio the room is not allowed to lose.

What the team says during the conversation is thrown away once it has been transcribed —
there the record is the text. A rehearsal take and the chunks of a back translation are the
opposite: the recording is the work, and a tablet that breaks with them still on it takes the
session with it.
"""

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room._deps import device_dep, room_key_dep
from app.core.database import get_db
from app.core.exceptions import ValidationError
from app.db.models.internalization_room import IRTakeKind
from app.models.internalization_room import TakeResponse, TakesResponse
from app.services import internalization_room as room
from app.services.internalization_room.takes import store_take, takes_of

router = APIRouter()


def _kind(raw: str) -> IRTakeKind:
    try:
        return IRTakeKind(raw)
    except ValueError:
        raise ValidationError(f"Unknown take kind: {raw}") from None


@router.post(
    "/sessions/{session_id}/takes",
    response_model=TakeResponse,
    dependencies=[room_key_dep],
)
async def keep_take(
    session_id: str,
    kind: str = Form(...),
    scope: str = Form(...),
    pass_number: int | None = Form(default=None),
    chunk_index: int | None = Form(default=None),
    file: UploadFile = File(...),
    device_id: str = device_dep,
    db: AsyncSession = Depends(get_db),
) -> TakeResponse:
    """Store one take and answer with where it landed.

    The app keeps its local copy until this answers, and re-sends the same bytes after a lost
    connection without checking anything first. That is safe because the key is the hash of
    the audio: a repeat lands on the same object and returns the row that already exists.
    """
    session = await room.get_session(db, session_id)
    take = await store_take(
        db,
        session_id=session.id,
        device_id=device_id,
        pericope=session.pericope,
        kind=_kind(kind),
        scope=scope,
        audio=await file.read(),
        pass_number=pass_number,
        chunk_index=chunk_index,
        content_type=file.content_type or "audio/mp4",
    )
    return TakeResponse(
        take_id=take.id,
        session_id=take.session_id,
        kind=take.kind.value,
        scope=take.scope,
        sha256=take.sha256,
        size_bytes=take.size_bytes,
    )


@router.get(
    "/sessions/{session_id}/takes",
    response_model=TakesResponse,
    dependencies=[room_key_dep],
)
async def list_takes(session_id: str, db: AsyncSession = Depends(get_db)) -> TakesResponse:
    session = await room.get_session(db, session_id)
    return TakesResponse(
        session_id=session.id,
        takes=[
            TakeResponse(
                take_id=take.id,
                session_id=take.session_id,
                kind=take.kind.value,
                scope=take.scope,
                sha256=take.sha256,
                size_bytes=take.size_bytes,
            )
            for take in await takes_of(db, session.id)
        ],
    )
