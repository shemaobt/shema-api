from fastapi import APIRouter, status

from app.api.annotation_studio._deps import CurrentUser, Db
from app.models.annotation_studio import (
    TierARecordingCreate,
    TierARecordingResponse,
    TierARecordingTicket,
    UploadTicket,
    WordCreate,
    WordReferenceCreate,
    WordResponse,
    WordUpdate,
)
from app.services.annotation_studio import access, tier_a_service

router = APIRouter()


@router.get("/languages/{language_id}/tier-a/words", response_model=list[WordResponse])
async def list_words(language_id: str, db: Db, user: CurrentUser) -> list[WordResponse]:
    await access.assert_language_access(db, user, language_id)
    words = await tier_a_service.list_words(db, language_id)
    return [WordResponse.model_validate(w) for w in words]


@router.post(
    "/languages/{language_id}/tier-a/words",
    response_model=WordResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_word(
    language_id: str, payload: WordCreate, db: Db, user: CurrentUser
) -> WordResponse:
    await access.assert_language_access(db, user, language_id)
    word = await tier_a_service.create_word(db, language_id, payload.gloss, payload.emblem)
    return WordResponse.model_validate(word)


@router.patch("/tier-a/words/{word_id}", response_model=WordResponse)
async def update_word(word_id: str, payload: WordUpdate, db: Db, user: CurrentUser) -> WordResponse:
    await access.assert_language_access(db, user, await access.language_id_for_word(db, word_id))
    word = await tier_a_service.update_word(db, word_id, **payload.model_dump(exclude_unset=True))
    return WordResponse.model_validate(word)


@router.delete("/tier-a/words/{word_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_word(word_id: str, db: Db, user: CurrentUser) -> None:
    await access.assert_language_access(db, user, await access.language_id_for_word(db, word_id))
    await tier_a_service.delete_word(db, word_id)


@router.post(
    "/tier-a/words/{word_id}/reference",
    response_model=UploadTicket,
    status_code=status.HTTP_201_CREATED,
)
async def set_reference(
    word_id: str, payload: WordReferenceCreate, db: Db, user: CurrentUser
) -> UploadTicket:
    await access.assert_language_access(db, user, await access.language_id_for_word(db, word_id))
    _word, presigned = await tier_a_service.set_reference(db, word_id, payload.upload_format)
    return UploadTicket.from_presigned(presigned)


@router.post("/tier-a/words/{word_id}/reference/complete", response_model=WordResponse)
async def complete_reference(word_id: str, db: Db, user: CurrentUser) -> WordResponse:
    await access.assert_language_access(db, user, await access.language_id_for_word(db, word_id))
    word = await tier_a_service.complete_reference(db, word_id)
    return WordResponse.model_validate(word)


@router.delete("/tier-a/words/{word_id}/reference", response_model=WordResponse)
async def clear_reference(word_id: str, db: Db, user: CurrentUser) -> WordResponse:
    await access.assert_language_access(db, user, await access.language_id_for_word(db, word_id))
    word = await tier_a_service.clear_reference(db, word_id)
    return WordResponse.model_validate(word)


@router.get(
    "/languages/{language_id}/tier-a/recordings",
    response_model=list[TierARecordingResponse],
)
async def list_recordings(
    language_id: str, db: Db, user: CurrentUser
) -> list[TierARecordingResponse]:
    await access.assert_language_access(db, user, language_id)
    recordings = await tier_a_service.list_recordings(db, language_id)
    return [TierARecordingResponse.model_validate(r) for r in recordings]


@router.post(
    "/tier-a/words/{word_id}/recordings",
    response_model=TierARecordingTicket,
    status_code=status.HTTP_201_CREATED,
)
async def create_recording(
    word_id: str, payload: TierARecordingCreate, db: Db, user: CurrentUser
) -> TierARecordingTicket:
    await access.assert_language_access(db, user, await access.language_id_for_word(db, word_id))
    recording, presigned = await tier_a_service.create_recording(
        db,
        word_id,
        payload.speaker_id,
        payload.rep_index,
        payload.upload_format,
        payload.duration_ms,
    )
    return TierARecordingTicket(
        recording=TierARecordingResponse.model_validate(recording),
        upload=UploadTicket.from_presigned(presigned),
    )


@router.post("/tier-a/recordings/{recording_id}/complete", response_model=TierARecordingResponse)
async def complete_recording(
    recording_id: str, db: Db, user: CurrentUser
) -> TierARecordingResponse:
    await access.assert_language_access(
        db, user, await access.language_id_for_recording_a(db, recording_id)
    )
    recording = await tier_a_service.complete_recording(db, recording_id)
    return TierARecordingResponse.model_validate(recording)


@router.delete("/tier-a/recordings/{recording_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_recording(recording_id: str, db: Db, user: CurrentUser) -> None:
    await access.assert_language_access(
        db, user, await access.language_id_for_recording_a(db, recording_id)
    )
    await tier_a_service.delete_recording(db, recording_id)
