from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_middleware import get_current_user
from app.core.database import get_db
from app.db.models.auth import User
from app.models.oc_recording import (
    CleaningStatusResponse,
    ConfirmUploadRequest,
    RecordingCreate,
    RecordingResponse,
    RecordingUpdate,
    ResumableUploadUrlRequest,
    ResumableUploadUrlResponse,
    SplitRequest,
    SplitStatusResponse,
    UploadUrlRequest,
    UploadUrlResponse,
)
from app.services.oral_collector import cleaning_service, recording_service, split_service

recordings_router = APIRouter()


@recordings_router.get("", response_model=list[RecordingResponse])
async def list_recordings(
    project_id: str = Query(..., description="Filter by project"),
    genre_id: str | None = Query(None),
    subcategory_id: str | None = Query(None),
    upload_status: str | None = Query(None),
    cleaning_status: str | None = Query(None),
    user_id: str | None = Query(None, description="Filter by recording author"),
    storyteller_id: str | None = Query(None, description="Filter by storyteller"),
    title: str | None = Query(None, description="Filter by exact (trimmed) title"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[RecordingResponse]:

    recordings = await recording_service.list_recordings(
        db,
        project_id,
        genre_id=genre_id,
        subcategory_id=subcategory_id,
        upload_status=upload_status,
        cleaning_status=cleaning_status,
        user_id=user_id,
        storyteller_id=storyteller_id,
        title=title,
        offset=offset,
        limit=limit,
    )
    return [RecordingResponse.model_validate(r) for r in recordings]


@recordings_router.get("/{recording_id}", response_model=RecordingResponse)
async def get_recording(
    recording_id: str,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RecordingResponse:

    recording = await recording_service.get_recording(db, recording_id)
    return RecordingResponse.model_validate(recording)


@recordings_router.post(
    "",
    response_model=RecordingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_recording(
    payload: RecordingCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RecordingResponse:

    recording = await recording_service.create_recording(db, payload, user.id)
    return RecordingResponse.model_validate(recording)


@recordings_router.patch("/{recording_id}", response_model=RecordingResponse)
async def update_recording(
    recording_id: str,
    payload: RecordingUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RecordingResponse:

    existing = await recording_service.get_recording(db, recording_id)
    await recording_service.check_recording_access(db, existing, user.id)
    recording = await recording_service.update_recording(db, recording_id, payload)
    return RecordingResponse.model_validate(recording)


@recordings_router.delete("/{recording_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_recording(
    recording_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:

    existing = await recording_service.get_recording(db, recording_id)
    await recording_service.check_recording_access(db, existing, user.id)
    await recording_service.delete_recording(db, recording_id)


@recordings_router.post("/clear-stale")
async def clear_stale_recordings(
    project_id: str = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:

    deleted = await recording_service.clear_stale_recordings(
        db, project_id, user.id, is_platform_admin=user.is_platform_admin
    )
    return {"deleted": deleted}


@recordings_router.post("/upload-url", response_model=UploadUrlResponse)
async def request_upload_url(
    payload: UploadUrlRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UploadUrlResponse:

    return await recording_service.generate_upload_url(
        db, payload.recording_id, payload.format, user.id
    )


@recordings_router.post("/resumable-upload-url", response_model=ResumableUploadUrlResponse)
async def request_resumable_upload_url(
    payload: ResumableUploadUrlRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResumableUploadUrlResponse:

    origin = request.headers.get("origin")
    return await recording_service.generate_resumable_upload_url(
        db, payload.recording_id, payload.format, user.id, origin=origin
    )


@recordings_router.post("/{recording_id}/confirm-upload", response_model=RecordingResponse)
async def confirm_upload(
    recording_id: str,
    payload: ConfirmUploadRequest | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RecordingResponse:

    existing = await recording_service.get_recording(db, recording_id)
    await recording_service.check_recording_access(db, existing, user.id)
    md5_hash = payload.md5_hash if payload else None
    crc32c = payload.crc32c if payload else None
    recording = await recording_service.confirm_upload(
        db, recording_id, md5_hash=md5_hash, crc32c=crc32c
    )
    return RecordingResponse.model_validate(recording)


@recordings_router.post(
    "/{recording_id}/split",
    response_model=RecordingResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def request_split(
    recording_id: str,
    payload: SplitRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RecordingResponse:

    recording = await split_service.request_split(db, recording_id, payload.segments, user.id)
    return RecordingResponse.model_validate(recording)


@recordings_router.get("/{recording_id}/split-status", response_model=SplitStatusResponse)
async def get_split_status(
    recording_id: str,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SplitStatusResponse:

    recording, segment_ids = await split_service.get_split_status(db, recording_id)
    return SplitStatusResponse(
        recording_id=recording.id,
        splitting_status=recording.splitting_status,
        segment_ids=segment_ids,
    )


@recordings_router.post(
    "/{recording_id}/clean",
    response_model=RecordingResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_cleaning(
    recording_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RecordingResponse:

    recording = await cleaning_service.trigger_cleaning(db, recording_id, user.id)
    return RecordingResponse.model_validate(recording)


@recordings_router.get("/{recording_id}/clean-status", response_model=CleaningStatusResponse)
async def get_cleaning_status(
    recording_id: str,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CleaningStatusResponse:

    recording = await cleaning_service.get_cleaning_status(db, recording_id)
    return CleaningStatusResponse(
        recording_id=recording.id,
        cleaning_status=recording.cleaning_status,
        cleaning_error=recording.cleaning_error,
    )
