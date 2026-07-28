from fastapi import APIRouter, status

from app.api.annotation_studio._deps import CurrentUser, Db
from app.core.as_enums import AsSortRound as SortRound
from app.models.annotation_studio import (
    ClipCreate,
    ClipResponse,
    ClipTicket,
    ReliabilityResponse,
    SortAssignmentRequest,
    SortAssignmentResponse,
    UploadTicket,
)
from app.services.annotation_studio import access, tier_c_service

router = APIRouter()


@router.get("/languages/{language_id}/tier-c/clips", response_model=list[ClipResponse])
async def list_clips(language_id: str, db: Db, user: CurrentUser) -> list[ClipResponse]:
    await access.assert_language_access(db, user, language_id)
    clips = await tier_c_service.list_clips(db, language_id)
    return [ClipResponse.model_validate(c) for c in clips]


@router.post(
    "/languages/{language_id}/tier-c/clips",
    response_model=ClipTicket,
    status_code=status.HTTP_201_CREATED,
)
async def create_clip(
    language_id: str, payload: ClipCreate, db: Db, user: CurrentUser
) -> ClipTicket:
    await access.assert_language_access(db, user, language_id)
    clip, presigned = await tier_c_service.create_clip(
        db,
        language_id,
        payload.clip_number,
        payload.upload_format,
        payload.source_recording_id,
        payload.source_word_text,
        payload.position,
        payload.duration_ms,
    )
    return ClipTicket(
        clip=ClipResponse.model_validate(clip),
        upload=UploadTicket.from_presigned(presigned),
    )


@router.post("/tier-c/clips/{clip_id}/complete", response_model=ClipResponse)
async def complete_clip(clip_id: str, db: Db, user: CurrentUser) -> ClipResponse:
    await access.assert_language_access(db, user, await access.language_id_for_clip(db, clip_id))
    clip = await tier_c_service.complete_clip(db, clip_id)
    return ClipResponse.model_validate(clip)


@router.delete("/tier-c/clips/{clip_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_clip(clip_id: str, db: Db, user: CurrentUser) -> None:
    await access.assert_language_access(db, user, await access.language_id_for_clip(db, clip_id))
    await tier_c_service.delete_clip(db, clip_id)


@router.put("/tier-c/clips/{clip_id}/sort", response_model=SortAssignmentResponse)
async def upsert_sort(
    clip_id: str, payload: SortAssignmentRequest, db: Db, user: CurrentUser
) -> SortAssignmentResponse:
    await access.assert_language_access(db, user, await access.language_id_for_clip(db, clip_id))
    assignment = await tier_c_service.upsert_sort(
        db, clip_id, payload.dimension, payload.round, payload.group_label
    )
    return SortAssignmentResponse(
        clip_id=assignment.clip_id,
        export_clip_id="",
        dimension=assignment.dimension,
        round=assignment.round,
        group_label=assignment.group_label,
    )


@router.get(
    "/languages/{language_id}/tier-c/assignments",
    response_model=list[SortAssignmentResponse],
)
async def list_assignments(
    language_id: str,
    dimension: str,
    db: Db,
    user: CurrentUser,
    round: str = SortRound.NORMAL.value,
) -> list[SortAssignmentResponse]:
    await access.assert_language_access(db, user, language_id)
    pairs = await tier_c_service.list_assignments(db, language_id, dimension, round)
    return [
        SortAssignmentResponse(
            clip_id=clip.id,
            export_clip_id=clip.export_clip_id,
            dimension=assignment.dimension,
            round=assignment.round,
            group_label=assignment.group_label,
        )
        for assignment, clip in pairs
    ]


@router.get("/languages/{language_id}/tier-c/reliability", response_model=ReliabilityResponse)
async def reliability(
    language_id: str, dimension: str, db: Db, user: CurrentUser
) -> ReliabilityResponse:
    await access.assert_language_access(db, user, language_id)
    result = await tier_c_service.reliability(db, language_id, dimension)
    return ReliabilityResponse(**result)
