from fastapi import APIRouter, status

from app.api.annotation_studio._deps import CurrentUser, Db
from app.models.annotation_studio import (
    PairCreate,
    PairResponse,
    PairUpdate,
    TierBRecordingCreate,
    TierBRecordingResponse,
    TierBRecordingTicket,
    UploadTicket,
)
from app.services.annotation_studio import access, tier_b_service

router = APIRouter()


@router.get("/languages/{language_id}/tier-b/pairs", response_model=list[PairResponse])
async def list_pairs(language_id: str, db: Db, user: CurrentUser) -> list[PairResponse]:
    await access.assert_language_access(db, user, language_id)
    pairs = await tier_b_service.list_pairs(db, language_id)
    return [PairResponse.model_validate(p) for p in pairs]


@router.post(
    "/languages/{language_id}/tier-b/pairs",
    response_model=PairResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_pair(
    language_id: str, payload: PairCreate, db: Db, user: CurrentUser
) -> PairResponse:
    await access.assert_language_access(db, user, language_id)
    pair = await tier_b_service.create_pair(
        db,
        language_id,
        payload.pair_number,
        payload.word_a_text,
        payload.word_b_text,
        payload.speaker_id,
    )
    return PairResponse.model_validate(pair)


@router.patch("/tier-b/pairs/{pair_id}", response_model=PairResponse)
async def update_pair(pair_id: str, payload: PairUpdate, db: Db, user: CurrentUser) -> PairResponse:
    await access.assert_language_access(db, user, await access.language_id_for_pair(db, pair_id))
    pair = await tier_b_service.update_pair(db, pair_id, payload.word_a_text, payload.word_b_text)
    return PairResponse.model_validate(pair)


@router.delete("/tier-b/pairs/{pair_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pair(pair_id: str, db: Db, user: CurrentUser) -> None:
    await access.assert_language_access(db, user, await access.language_id_for_pair(db, pair_id))
    await tier_b_service.delete_pair(db, pair_id)


@router.get(
    "/languages/{language_id}/tier-b/recordings",
    response_model=list[TierBRecordingResponse],
)
async def list_recordings(
    language_id: str, db: Db, user: CurrentUser
) -> list[TierBRecordingResponse]:
    await access.assert_language_access(db, user, language_id)
    recordings = await tier_b_service.list_recordings(db, language_id)
    return [TierBRecordingResponse.model_validate(r) for r in recordings]


@router.post(
    "/tier-b/pairs/{pair_id}/recordings",
    response_model=TierBRecordingTicket,
    status_code=status.HTTP_201_CREATED,
)
async def create_recording(
    pair_id: str, payload: TierBRecordingCreate, db: Db, user: CurrentUser
) -> TierBRecordingTicket:
    await access.assert_language_access(db, user, await access.language_id_for_pair(db, pair_id))
    recording, presigned = await tier_b_service.create_recording(
        db, pair_id, payload.side, payload.rep_index, payload.upload_format, payload.duration_ms
    )
    return TierBRecordingTicket(
        recording=TierBRecordingResponse.model_validate(recording),
        upload=UploadTicket.from_presigned(presigned),
    )


@router.post("/tier-b/recordings/{recording_id}/complete", response_model=TierBRecordingResponse)
async def complete_recording(
    recording_id: str, db: Db, user: CurrentUser
) -> TierBRecordingResponse:
    await access.assert_language_access(
        db, user, await access.language_id_for_recording_b(db, recording_id)
    )
    recording = await tier_b_service.complete_recording(db, recording_id)
    return TierBRecordingResponse.model_validate(recording)


@router.delete("/tier-b/recordings/{recording_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_recording(recording_id: str, db: Db, user: CurrentUser) -> None:
    await access.assert_language_access(
        db, user, await access.language_id_for_recording_b(db, recording_id)
    )
    await tier_b_service.delete_recording(db, recording_id)
