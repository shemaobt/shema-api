from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import CleaningStatus, SplittingStatus, UploadStatus
from app.core.exceptions import (
    AuthorizationError,
    ConflictError,
    InvalidCleaningStatusError,
    NotFoundError,
    SecondaryClassificationConflictError,
    UnknownReferenceError,
    ValidationError,
)
from app.db.models.oc_genre import OC_Genre, OC_Subcategory
from app.db.models.oc_recording import OC_Recording
from app.db.models.project import ProjectUserAccess
from app.models.oc_recording import (
    ConfirmUploadRequest,
    RecordingCreate,
    RecordingUpdate,
    ResumableUploadUrlRequest,
    ResumableUploadUrlResponse,
)
from tests.baker import (
    make_language,
    make_oc_recording,
    make_oc_storyteller,
    make_oc_taxonomy,
    make_project,
    make_user,
)

pytest.importorskip("app.inngest")


async def _seed_project(db: AsyncSession) -> str:
    lang = await make_language(db)
    project = await make_project(db, lang.id)
    return project.id


def _import_service():
    from app.services.oral_collector import recording_service

    return recording_service


@pytest.mark.asyncio
async def test_create_recording(db_session: AsyncSession) -> None:
    rs = _import_service()
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre, sub = await make_oc_taxonomy(db_session)

    data = RecordingCreate(
        description="a description long enough to satisfy the rule",
        project_id=project_id,
        genre_id=genre.id,
        subcategory_id=sub.id,
        title="My Recording",
        duration_seconds=30.5,
        file_size_bytes=2048,
        format="m4a",
        recorded_at=datetime.now(UTC),
    )
    rec = await rs.create_recording(db_session, data, user.id)

    assert rec.id is not None
    assert rec.project_id == project_id
    assert rec.user_id == user.id
    assert rec.title == "My Recording"
    assert rec.duration_seconds == 30.5
    assert rec.file_size_bytes == 2048
    assert rec.format == "m4a"
    assert rec.upload_status == UploadStatus.LOCAL


@pytest.mark.asyncio
async def test_create_recording_with_description(db_session: AsyncSession) -> None:
    rs = _import_service()
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre, sub = await make_oc_taxonomy(db_session)

    data = RecordingCreate(
        project_id=project_id,
        genre_id=genre.id,
        subcategory_id=sub.id,
        description="Field recording from coastal village",
        duration_seconds=12.0,
        file_size_bytes=4096,
        format="m4a",
        recorded_at=datetime.now(UTC),
    )
    rec = await rs.create_recording(db_session, data, user.id)

    assert rec.description == "Field recording from coastal village"


@pytest.mark.asyncio
async def test_update_recording_sets_description(db_session: AsyncSession) -> None:
    from app.models.oc_recording import RecordingUpdate

    rs = _import_service()
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre, sub = await make_oc_taxonomy(db_session)
    rec = await make_oc_recording(
        db_session, project_id, genre.id, sub.id, user_id=user.id, upload_status=UploadStatus.LOCAL
    )

    story = "A new story, told at length enough to be worth keeping"
    updated = await rs.update_recording(db_session, rec.id, RecordingUpdate(description=story))
    assert updated.description == story


@pytest.mark.asyncio
async def test_update_recording_sets_cleaning_status(db_session: AsyncSession) -> None:
    rs = _import_service()
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre, sub = await make_oc_taxonomy(db_session)
    rec = await make_oc_recording(
        db_session, project_id, genre.id, sub.id, user_id=user.id, upload_status=UploadStatus.LOCAL
    )
    assert rec.cleaning_status == CleaningStatus.NONE

    updated = await rs.update_recording(
        db_session, rec.id, RecordingUpdate(cleaning_status=CleaningStatus.NEEDS_CLEANING)
    )
    assert updated.cleaning_status == CleaningStatus.NEEDS_CLEANING

    cleared = await rs.update_recording(
        db_session, rec.id, RecordingUpdate(cleaning_status=CleaningStatus.NONE)
    )
    assert cleared.cleaning_status == CleaningStatus.NONE


@pytest.mark.asyncio
async def test_update_recording_rejects_internal_cleaning_status(
    db_session: AsyncSession,
) -> None:
    rs = _import_service()
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre, sub = await make_oc_taxonomy(db_session)
    rec = await make_oc_recording(
        db_session, project_id, genre.id, sub.id, user_id=user.id, upload_status=UploadStatus.LOCAL
    )

    for internal_status in (CleaningStatus.CLEANING, CleaningStatus.CLEANED, CleaningStatus.FAILED):
        with pytest.raises(InvalidCleaningStatusError):
            await rs.update_recording(
                db_session, rec.id, RecordingUpdate(cleaning_status=internal_status)
            )


@pytest.mark.asyncio
async def test_get_recording(db_session: AsyncSession) -> None:
    rs = _import_service()
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre, sub = await make_oc_taxonomy(db_session)

    rec = await make_oc_recording(
        db_session, project_id, genre.id, sub.id, user_id=user.id, upload_status=UploadStatus.LOCAL
    )
    fetched = await rs.get_recording(db_session, rec.id)

    assert fetched.id == rec.id
    assert fetched.title == "test recording"


@pytest.mark.asyncio
async def test_get_recording_not_found(db_session: AsyncSession) -> None:
    rs = _import_service()
    with pytest.raises(NotFoundError):
        await rs.get_recording(db_session, "nonexistent-id")


@pytest.mark.asyncio
async def test_update_recording(db_session: AsyncSession) -> None:
    rs = _import_service()
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre, sub = await make_oc_taxonomy(db_session)

    rec = await make_oc_recording(
        db_session, project_id, genre.id, sub.id, user_id=user.id, upload_status=UploadStatus.LOCAL
    )
    updated = await rs.update_recording(db_session, rec.id, RecordingUpdate(title="Updated Title"))

    assert updated.title == "Updated Title"


@pytest.mark.asyncio
async def test_delete_recording(db_session: AsyncSession) -> None:
    rs = _import_service()
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre, sub = await make_oc_taxonomy(db_session)

    rec = await make_oc_recording(
        db_session, project_id, genre.id, sub.id, user_id=user.id, upload_status=UploadStatus.LOCAL
    )
    await rs.delete_recording(db_session, rec.id)

    with pytest.raises(NotFoundError):
        await rs.get_recording(db_session, rec.id)


@pytest.mark.asyncio
async def test_list_recordings(db_session: AsyncSession) -> None:
    rs = _import_service()
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre, sub = await make_oc_taxonomy(db_session)

    await make_oc_recording(
        db_session,
        project_id,
        genre.id,
        sub.id,
        user_id=user.id,
        upload_status=UploadStatus.UPLOADED,
    )
    await make_oc_recording(
        db_session,
        project_id,
        genre.id,
        sub.id,
        user_id=user.id,
        upload_status=UploadStatus.VERIFIED,
        title="Second recording",
    )

    recordings = await rs.list_recordings(db_session, project_id)
    assert len(recordings) == 2


@pytest.mark.asyncio
async def test_list_recordings_filter_by_status(db_session: AsyncSession) -> None:
    rs = _import_service()
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre, sub = await make_oc_taxonomy(db_session)

    await make_oc_recording(
        db_session,
        project_id,
        genre.id,
        sub.id,
        user_id=user.id,
        upload_status=UploadStatus.UPLOADED,
    )
    await make_oc_recording(
        db_session,
        project_id,
        genre.id,
        sub.id,
        user_id=user.id,
        upload_status=UploadStatus.LOCAL,
        title="Second recording",
    )

    uploaded = await rs.list_recordings(db_session, project_id, upload_status=UploadStatus.UPLOADED)
    assert len(uploaded) == 1
    assert uploaded[0].upload_status == UploadStatus.UPLOADED


@pytest.mark.asyncio
async def test_check_recording_access_owner(db_session: AsyncSession) -> None:
    rs = _import_service()
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre, sub = await make_oc_taxonomy(db_session)

    rec = await make_oc_recording(
        db_session, project_id, genre.id, sub.id, user_id=user.id, upload_status=UploadStatus.LOCAL
    )
    await rs.check_recording_access(db_session, rec, user.id)


@pytest.mark.asyncio
async def test_check_recording_access_denied(db_session: AsyncSession) -> None:
    rs = _import_service()
    user = await make_user(db_session, email="owner@test.com")
    other = await make_user(db_session, email="other@test.com")
    project_id = await _seed_project(db_session)
    genre, sub = await make_oc_taxonomy(db_session)

    rec = await make_oc_recording(
        db_session, project_id, genre.id, sub.id, user_id=user.id, upload_status=UploadStatus.LOCAL
    )
    with pytest.raises(AuthorizationError):
        await rs.check_recording_access(db_session, rec, other.id)


@pytest.mark.asyncio
async def test_check_recording_access_manager(db_session: AsyncSession) -> None:
    rs = _import_service()
    user = await make_user(db_session, email="owner@test.com")
    manager = await make_user(db_session, email="manager@test.com")
    project_id = await _seed_project(db_session)
    genre, sub = await make_oc_taxonomy(db_session)

    access = ProjectUserAccess(project_id=project_id, user_id=manager.id, role="manager")
    db_session.add(access)
    await db_session.commit()

    rec = await make_oc_recording(
        db_session, project_id, genre.id, sub.id, user_id=user.id, upload_status=UploadStatus.LOCAL
    )
    await rs.check_recording_access(db_session, rec, manager.id)


def test_gcs_blob_path() -> None:
    rs = _import_service()
    path = rs._gcs_blob_path("proj-1", "genre-1", "rec-1", "m4a")
    assert path == "oral-collector/proj-1/genre-1/rec-1.m4a"


def test_gcs_blob_path_wav() -> None:
    rs = _import_service()
    path = rs._gcs_blob_path("proj-1", "genre-1", "rec-1", "wav")
    assert path == "oral-collector/proj-1/genre-1/rec-1.wav"


def test_confirm_upload_request_model() -> None:
    req = ConfirmUploadRequest(md5_hash="abc123")
    assert req.md5_hash == "abc123"
    assert req.crc32c is None

    req_none = ConfirmUploadRequest()
    assert req_none.md5_hash is None
    assert req_none.crc32c is None

    req_crc = ConfirmUploadRequest(crc32c="Nks/tw==")
    assert req_crc.crc32c == "Nks/tw=="
    assert req_crc.md5_hash is None


def test_resumable_upload_url_request_model() -> None:
    req = ResumableUploadUrlRequest(recording_id="rec-1", format="m4a")
    assert req.recording_id == "rec-1"
    assert req.format == "m4a"


def test_resumable_upload_url_response_model() -> None:
    resp = ResumableUploadUrlResponse(
        recording_id="rec-1",
        session_uri="https://example.com/upload",
        chunk_size_bytes=8388608,
        content_type="audio/mp4",
    )
    assert resp.session_uri == "https://example.com/upload"
    assert resp.chunk_size_bytes == 8388608


@pytest.mark.asyncio
async def test_create_recording_with_storyteller(db_session: AsyncSession) -> None:
    rs = _import_service()
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre, sub = await make_oc_taxonomy(db_session)
    storyteller = await make_oc_storyteller(
        db_session, project_id, external_acceptance_confirmed=True
    )

    data = RecordingCreate(
        description="a description long enough to satisfy the rule",
        project_id=project_id,
        genre_id=genre.id,
        subcategory_id=sub.id,
        storyteller_id=storyteller.id,
        duration_seconds=12.0,
        file_size_bytes=4096,
        format="m4a",
        recorded_at=datetime.now(UTC),
    )
    rec = await rs.create_recording(db_session, data, user.id)
    assert rec.storyteller_id == storyteller.id


@pytest.mark.asyncio
async def test_create_recording_rejects_cross_project_storyteller(
    db_session: AsyncSession,
) -> None:
    rs = _import_service()
    user = await make_user(db_session)
    project_id_a = await _seed_project(db_session)

    lang_b = await make_language(db_session, name="Other", code="oth")
    from tests.baker import make_project as _make_project

    project_b = await _make_project(db_session, lang_b.id, name="Other Project")
    storyteller_b = await make_oc_storyteller(
        db_session, project_b.id, external_acceptance_confirmed=True
    )

    genre, sub = await make_oc_taxonomy(db_session)
    data = RecordingCreate(
        description="a description long enough to satisfy the rule",
        project_id=project_id_a,
        genre_id=genre.id,
        subcategory_id=sub.id,
        storyteller_id=storyteller_b.id,
        duration_seconds=12.0,
        file_size_bytes=4096,
        format="m4a",
        recorded_at=datetime.now(UTC),
    )
    with pytest.raises(ValidationError):
        await rs.create_recording(db_session, data, user.id)


@pytest.mark.asyncio
async def test_update_recording_rejects_cross_project_storyteller(
    db_session: AsyncSession,
) -> None:
    rs = _import_service()
    user = await make_user(db_session)
    project_id_a = await _seed_project(db_session)
    genre, sub = await make_oc_taxonomy(db_session)
    rec = await make_oc_recording(
        db_session,
        project_id_a,
        genre.id,
        sub.id,
        user_id=user.id,
        upload_status=UploadStatus.LOCAL,
    )

    lang_b = await make_language(db_session, name="Other", code="oth")
    from tests.baker import make_project as _make_project

    project_b = await _make_project(db_session, lang_b.id, name="Other Project")
    storyteller_b = await make_oc_storyteller(
        db_session, project_b.id, external_acceptance_confirmed=True
    )

    with pytest.raises(ValidationError):
        await rs.update_recording(
            db_session, rec.id, RecordingUpdate(storyteller_id=storyteller_b.id)
        )


@pytest.mark.asyncio
async def test_create_recording_with_secondary_classification(
    db_session: AsyncSession,
) -> None:
    rs = _import_service()
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre, sub = await make_oc_taxonomy(db_session)

    genre_b = OC_Genre(name="wisdom", sort_order=1)
    db_session.add(genre_b)
    await db_session.flush()
    sub_b = OC_Subcategory(genre_id=genre_b.id, name="proverb", sort_order=0)
    db_session.add(sub_b)
    await db_session.commit()
    await db_session.refresh(genre_b)
    await db_session.refresh(sub_b)

    data = RecordingCreate(
        description="a description long enough to satisfy the rule",
        project_id=project_id,
        genre_id=genre.id,
        subcategory_id=sub.id,
        secondary_genre_id=genre_b.id,
        secondary_subcategory_id=sub_b.id,
        secondary_register_id="consultative",
        duration_seconds=12.0,
        file_size_bytes=4096,
        format="m4a",
        recorded_at=datetime.now(UTC),
    )
    rec = await rs.create_recording(db_session, data, user.id)
    assert rec.secondary_genre_id == genre_b.id
    assert rec.secondary_subcategory_id == sub_b.id
    assert rec.secondary_register_id == "consultative"


@pytest.mark.asyncio
async def test_create_recording_allows_secondary_with_only_genre_matching_primary(
    db_session: AsyncSession,
) -> None:
    rs = _import_service()
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre, sub = await make_oc_taxonomy(db_session)

    other_sub = OC_Subcategory(genre_id=genre.id, name="other", sort_order=1)
    db_session.add(other_sub)
    await db_session.commit()
    await db_session.refresh(other_sub)

    data = RecordingCreate(
        description="a description long enough to satisfy the rule",
        project_id=project_id,
        genre_id=genre.id,
        subcategory_id=sub.id,
        register_id="formal",
        secondary_genre_id=genre.id,
        secondary_subcategory_id=other_sub.id,
        secondary_register_id="ceremonial",
        duration_seconds=1.0,
        file_size_bytes=1,
        format="m4a",
        recorded_at=datetime.now(UTC),
    )
    rec = await rs.create_recording(db_session, data, user.id)
    assert rec.secondary_genre_id == genre.id


@pytest.mark.asyncio
async def test_create_recording_rejects_identical_secondary_triple(
    db_session: AsyncSession,
) -> None:
    rs = _import_service()
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre, sub = await make_oc_taxonomy(db_session)

    data = RecordingCreate(
        description="a description long enough to satisfy the rule",
        project_id=project_id,
        genre_id=genre.id,
        subcategory_id=sub.id,
        register_id="formal",
        secondary_genre_id=genre.id,
        secondary_subcategory_id=sub.id,
        secondary_register_id="formal",
        duration_seconds=1.0,
        file_size_bytes=1,
        format="m4a",
        recorded_at=datetime.now(UTC),
    )
    with pytest.raises(SecondaryClassificationConflictError):
        await rs.create_recording(db_session, data, user.id)


@pytest.mark.asyncio
async def test_update_recording_allows_single_field_overlap_when_merged_triple_differs(
    db_session: AsyncSession,
) -> None:
    rs = _import_service()
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre, sub = await make_oc_taxonomy(db_session)
    rec = await make_oc_recording(
        db_session, project_id, genre.id, sub.id, user_id=user.id, upload_status=UploadStatus.LOCAL
    )
    rec.register_id = "formal"
    await db_session.commit()
    await db_session.refresh(rec)

    updated = await rs.update_recording(
        db_session,
        rec.id,
        RecordingUpdate(secondary_genre_id=genre.id),
    )
    assert updated.secondary_genre_id == genre.id


@pytest.mark.asyncio
async def test_update_recording_rejects_when_merged_triple_collapses_to_identical(
    db_session: AsyncSession,
) -> None:
    rs = _import_service()
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre, sub = await make_oc_taxonomy(db_session)
    rec = await make_oc_recording(
        db_session, project_id, genre.id, sub.id, user_id=user.id, upload_status=UploadStatus.LOCAL
    )
    rec.register_id = "formal"
    await db_session.commit()
    await db_session.refresh(rec)

    with pytest.raises(SecondaryClassificationConflictError):
        await rs.update_recording(
            db_session,
            rec.id,
            RecordingUpdate(
                secondary_genre_id=genre.id,
                secondary_subcategory_id=sub.id,
                secondary_register_id="formal",
            ),
        )


@pytest.mark.asyncio
async def test_update_recording_rejects_a_primary_only_update_that_lands_on_the_secondary(
    db_session: AsyncSession,
) -> None:
    """The direction the old genre-only rule could not see: the payload carries no
    secondary field at all, and the primary moves onto the stored secondary."""
    rs = _import_service()
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre, sub = await make_oc_taxonomy(db_session)
    rec = await make_oc_recording(
        db_session, project_id, genre.id, sub.id, user_id=user.id, upload_status=UploadStatus.LOCAL
    )
    rec.register_id = "formal"
    rec.secondary_genre_id = genre.id
    rec.secondary_subcategory_id = sub.id
    rec.secondary_register_id = "ceremonial"
    await db_session.commit()
    await db_session.refresh(rec)

    with pytest.raises(SecondaryClassificationConflictError):
        await rs.update_recording(db_session, rec.id, RecordingUpdate(register_id="ceremonial"))


@pytest.mark.asyncio
async def test_update_recording_allows_a_secondary_left_partly_unset(
    db_session: AsyncSession,
) -> None:
    """ENG-72 defines the comparison as `==` over all three fields, `None` included, so a
    secondary that matches on two fields and is unset on the third is not identical and
    stays allowed. The old genre-only rule rejected this; loosening it is the point."""
    rs = _import_service()
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre, sub = await make_oc_taxonomy(db_session)
    rec = await make_oc_recording(
        db_session, project_id, genre.id, sub.id, user_id=user.id, upload_status=UploadStatus.LOCAL
    )
    rec.register_id = "formal"
    await db_session.commit()
    await db_session.refresh(rec)

    updated = await rs.update_recording(
        db_session,
        rec.id,
        RecordingUpdate(secondary_genre_id=genre.id, secondary_subcategory_id=sub.id),
    )

    assert updated.secondary_register_id is None
    assert updated.secondary_subcategory_id == sub.id


@pytest.mark.asyncio
async def test_list_recordings_filter_by_user_and_storyteller(
    db_session: AsyncSession,
) -> None:
    rs = _import_service()
    user_a = await make_user(db_session, email="a@test.com")
    user_b = await make_user(db_session, email="b@test.com")
    project_id = await _seed_project(db_session)
    genre, sub = await make_oc_taxonomy(db_session)
    st_a = await make_oc_storyteller(
        db_session, project_id, name="Ana", external_acceptance_confirmed=True
    )
    st_b = await make_oc_storyteller(
        db_session, project_id, name="Beto", external_acceptance_confirmed=True
    )

    rec_a = await make_oc_recording(
        db_session,
        project_id,
        genre.id,
        sub.id,
        user_id=user_a.id,
        upload_status=UploadStatus.UPLOADED,
    )
    rec_b = await make_oc_recording(
        db_session,
        project_id,
        genre.id,
        sub.id,
        user_id=user_b.id,
        upload_status=UploadStatus.UPLOADED,
        title="User B recording",
    )
    rec_a.storyteller_id = st_a.id
    rec_b.storyteller_id = st_b.id
    await db_session.commit()

    by_user = await rs.list_recordings(db_session, project_id, user_id=user_a.id)
    assert {r.id for r in by_user} == {rec_a.id}

    by_st = await rs.list_recordings(db_session, project_id, storyteller_id=st_b.id)
    assert {r.id for r in by_st} == {rec_b.id}


@pytest.mark.asyncio
async def test_create_recording_rejects_duplicate_title(db_session: AsyncSession) -> None:
    rs = _import_service()
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre, sub = await make_oc_taxonomy(db_session)

    def _data(title: str) -> RecordingCreate:
        return RecordingCreate(
            description="a description long enough to satisfy the rule",
            project_id=project_id,
            genre_id=genre.id,
            subcategory_id=sub.id,
            title=title,
            duration_seconds=10.0,
            file_size_bytes=1024,
            format="m4a",
            recorded_at=datetime.now(UTC),
        )

    await rs.create_recording(db_session, _data("Genesis 1"), user.id)

    with pytest.raises(ConflictError):
        await rs.create_recording(db_session, _data("Genesis 1"), user.id)


@pytest.mark.asyncio
async def test_create_recording_normalizes_and_rejects_trimmed_duplicate(
    db_session: AsyncSession,
) -> None:
    rs = _import_service()
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre, sub = await make_oc_taxonomy(db_session)

    def _data(title: str) -> RecordingCreate:
        return RecordingCreate(
            description="a description long enough to satisfy the rule",
            project_id=project_id,
            genre_id=genre.id,
            subcategory_id=sub.id,
            title=title,
            duration_seconds=10.0,
            file_size_bytes=1024,
            format="m4a",
            recorded_at=datetime.now(UTC),
        )

    created = await rs.create_recording(db_session, _data("  Exodus  "), user.id)
    assert created.title == "Exodus"

    with pytest.raises(ConflictError):
        await rs.create_recording(db_session, _data("Exodus"), user.id)


@pytest.mark.asyncio
async def test_create_recording_title_match_is_case_sensitive(db_session: AsyncSession) -> None:
    rs = _import_service()
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre, sub = await make_oc_taxonomy(db_session)

    def _data(title: str) -> RecordingCreate:
        return RecordingCreate(
            description="a description long enough to satisfy the rule",
            project_id=project_id,
            genre_id=genre.id,
            subcategory_id=sub.id,
            title=title,
            duration_seconds=10.0,
            file_size_bytes=1024,
            format="m4a",
            recorded_at=datetime.now(UTC),
        )

    await rs.create_recording(db_session, _data("Psalm"), user.id)

    with pytest.raises(ConflictError):
        await rs.create_recording(db_session, _data("Psalm"), user.id)

    lowercase = await rs.create_recording(db_session, _data("psalm"), user.id)
    assert lowercase.title == "psalm"


@pytest.mark.asyncio
async def test_create_recording_blank_titles_do_not_collide(db_session: AsyncSession) -> None:
    rs = _import_service()
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre, sub = await make_oc_taxonomy(db_session)

    def _data(title: str) -> RecordingCreate:
        return RecordingCreate(
            description="a description long enough to satisfy the rule",
            project_id=project_id,
            genre_id=genre.id,
            subcategory_id=sub.id,
            title=title,
            duration_seconds=10.0,
            file_size_bytes=1024,
            format="m4a",
            recorded_at=datetime.now(UTC),
        )

    first = await rs.create_recording(db_session, _data("   "), user.id)
    second = await rs.create_recording(db_session, _data(""), user.id)

    assert first.id != second.id
    assert first.title is None
    assert second.title is None


@pytest.mark.asyncio
async def test_create_recording_ignores_split_children_for_uniqueness(
    db_session: AsyncSession,
) -> None:
    rs = _import_service()
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre, sub = await make_oc_taxonomy(db_session)

    split_child = OC_Recording(
        project_id=project_id,
        genre_id=genre.id,
        subcategory_id=sub.id,
        user_id=user.id,
        title="Ruth",
        split_from_id="parent-recording-id",
        duration_seconds=5.0,
        file_size_bytes=512,
        format="m4a",
        recorded_at=datetime.now(UTC),
    )
    db_session.add(split_child)
    await db_session.commit()

    data = RecordingCreate(
        description="a description long enough to satisfy the rule",
        project_id=project_id,
        genre_id=genre.id,
        subcategory_id=sub.id,
        title="Ruth",
        duration_seconds=10.0,
        file_size_bytes=1024,
        format="m4a",
        recorded_at=datetime.now(UTC),
    )
    created = await rs.create_recording(db_session, data, user.id)

    assert created.id != split_child.id
    assert created.title == "Ruth"


@pytest.mark.asyncio
async def test_update_recording_rejects_duplicate_title(db_session: AsyncSession) -> None:
    rs = _import_service()
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre, sub = await make_oc_taxonomy(db_session)

    await make_oc_recording(
        db_session, project_id, genre.id, sub.id, user_id=user.id, upload_status=UploadStatus.LOCAL
    )
    other = OC_Recording(
        project_id=project_id,
        genre_id=genre.id,
        subcategory_id=sub.id,
        user_id=user.id,
        title="Another Story",
        duration_seconds=5.0,
        file_size_bytes=512,
        format="m4a",
        recorded_at=datetime.now(UTC),
    )
    db_session.add(other)
    await db_session.commit()
    await db_session.refresh(other)

    with pytest.raises(ConflictError):
        await rs.update_recording(db_session, other.id, RecordingUpdate(title="test recording"))


@pytest.mark.asyncio
async def test_update_recording_keep_own_title_succeeds(db_session: AsyncSession) -> None:
    rs = _import_service()
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre, sub = await make_oc_taxonomy(db_session)

    rec = await make_oc_recording(
        db_session,
        project_id,
        genre.id,
        sub.id,
        user_id=user.id,
        title="test recording",
        upload_status=UploadStatus.LOCAL,
    )
    updated = await rs.update_recording(db_session, rec.id, RecordingUpdate(title="test recording"))

    assert updated.id == rec.id
    assert updated.title == "test recording"


@pytest.mark.asyncio
async def test_update_recording_trims_title(db_session: AsyncSession) -> None:
    rs = _import_service()
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre, sub = await make_oc_taxonomy(db_session)

    rec = await make_oc_recording(
        db_session, project_id, genre.id, sub.id, user_id=user.id, upload_status=UploadStatus.LOCAL
    )
    updated = await rs.update_recording(
        db_session, rec.id, RecordingUpdate(title="  Trimmed Title  ")
    )

    assert updated.title == "Trimmed Title"


@pytest.mark.asyncio
async def test_list_recordings_filter_by_title(db_session: AsyncSession) -> None:
    rs = _import_service()
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre, sub = await make_oc_taxonomy(db_session)

    for title in ("Alpha", "Beta"):
        db_session.add(
            OC_Recording(
                project_id=project_id,
                genre_id=genre.id,
                subcategory_id=sub.id,
                user_id=user.id,
                title=title,
                duration_seconds=5.0,
                file_size_bytes=512,
                format="m4a",
                upload_status=UploadStatus.UPLOADED,
                recorded_at=datetime.now(UTC),
            )
        )
    await db_session.commit()

    matched = await rs.list_recordings(db_session, project_id, title="Alpha")
    assert [r.title for r in matched] == ["Alpha"]

    trimmed = await rs.list_recordings(db_session, project_id, title="  Alpha  ")
    assert [r.title for r in trimmed] == ["Alpha"]

    missing = await rs.list_recordings(db_session, project_id, title="Gamma")
    assert missing == []


@pytest.mark.asyncio
async def test_create_recording_duplicate_title_allowed_across_projects(
    db_session: AsyncSession,
) -> None:
    rs = _import_service()
    user = await make_user(db_session)
    project_a = await _seed_project(db_session)
    lang_b = await make_language(db_session, name="Other", code="oth")
    project_b = await make_project(db_session, lang_b.id, name="Other Project")
    genre, sub = await make_oc_taxonomy(db_session)

    def _data(project_id: str) -> RecordingCreate:
        return RecordingCreate(
            description="a description long enough to satisfy the rule",
            project_id=project_id,
            genre_id=genre.id,
            subcategory_id=sub.id,
            title="Shared Title",
            duration_seconds=10.0,
            file_size_bytes=1024,
            format="m4a",
            recorded_at=datetime.now(UTC),
        )

    in_a = await rs.create_recording(db_session, _data(project_a), user.id)
    in_b = await rs.create_recording(db_session, _data(project_b.id), user.id)

    assert in_a.id != in_b.id
    assert in_a.title == in_b.title == "Shared Title"


@pytest.mark.asyncio
async def test_create_recording_allowed_when_title_held_by_archived_split_parent(
    db_session: AsyncSession,
) -> None:
    rs = _import_service()
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre, sub = await make_oc_taxonomy(db_session)

    archived_parent = OC_Recording(
        project_id=project_id,
        genre_id=genre.id,
        subcategory_id=sub.id,
        user_id=user.id,
        title="Genesis 1",
        splitting_status=SplittingStatus.ARCHIVED_AFTER_SPLIT,
        duration_seconds=20.0,
        file_size_bytes=2048,
        format="m4a",
        recorded_at=datetime.now(UTC),
    )
    db_session.add(archived_parent)
    await db_session.commit()

    data = RecordingCreate(
        description="a description long enough to satisfy the rule",
        project_id=project_id,
        genre_id=genre.id,
        subcategory_id=sub.id,
        title="Genesis 1",
        duration_seconds=10.0,
        file_size_bytes=1024,
        format="m4a",
        recorded_at=datetime.now(UTC),
    )
    created = await rs.create_recording(db_session, data, user.id)

    assert created.id != archived_parent.id
    assert created.title == "Genesis 1"


@pytest.mark.asyncio
async def test_update_recording_blank_title_clears_to_null(db_session: AsyncSession) -> None:
    rs = _import_service()
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre, sub = await make_oc_taxonomy(db_session)

    rec = await make_oc_recording(
        db_session, project_id, genre.id, sub.id, user_id=user.id, upload_status=UploadStatus.LOCAL
    )
    updated = await rs.update_recording(db_session, rec.id, RecordingUpdate(title="   "))

    assert updated.title is None


@pytest.mark.asyncio
async def test_duplicate_title_rejected_at_db_level(db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre, sub = await make_oc_taxonomy(db_session)

    await make_oc_recording(
        db_session,
        project_id,
        genre.id,
        sub.id,
        user_id=user.id,
        title="Genesis 1",
        upload_status=UploadStatus.LOCAL,
    )

    with pytest.raises(IntegrityError):
        await make_oc_recording(
            db_session,
            project_id,
            genre.id,
            sub.id,
            user_id=user.id,
            title="Genesis 1",
            upload_status=UploadStatus.LOCAL,
        )


@pytest.mark.asyncio
async def test_db_unique_index_exempts_split_children(db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre, sub = await make_oc_taxonomy(db_session)

    await make_oc_recording(
        db_session,
        project_id,
        genre.id,
        sub.id,
        user_id=user.id,
        title="Genesis 1",
        upload_status=UploadStatus.LOCAL,
    )
    split_child = OC_Recording(
        project_id=project_id,
        genre_id=genre.id,
        subcategory_id=sub.id,
        user_id=user.id,
        title="Genesis 1",
        split_from_id="parent-id",
        duration_seconds=5.0,
        file_size_bytes=512,
        format="m4a",
        recorded_at=datetime.now(UTC),
    )
    db_session.add(split_child)
    await db_session.commit()

    assert split_child.id is not None


@pytest.mark.asyncio
async def test_db_unique_index_exempts_archived_split_parent(
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre, sub = await make_oc_taxonomy(db_session)

    await make_oc_recording(
        db_session,
        project_id,
        genre.id,
        sub.id,
        user_id=user.id,
        title="Genesis 1",
        upload_status=UploadStatus.UPLOADED,
    )
    archived_parent = OC_Recording(
        project_id=project_id,
        genre_id=genre.id,
        subcategory_id=sub.id,
        user_id=user.id,
        title="Genesis 1",
        splitting_status=SplittingStatus.ARCHIVED_AFTER_SPLIT,
        duration_seconds=5.0,
        file_size_bytes=512,
        format="m4a",
        recorded_at=datetime.now(UTC),
    )
    db_session.add(archived_parent)
    await db_session.commit()

    assert archived_parent.id is not None


@pytest.mark.asyncio
async def test_db_unique_index_allows_repeated_null_titles(
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre, sub = await make_oc_taxonomy(db_session)

    first = await make_oc_recording(
        db_session,
        project_id,
        genre.id,
        sub.id,
        user_id=user.id,
        title=None,
        upload_status=UploadStatus.LOCAL,
    )
    second = await make_oc_recording(
        db_session,
        project_id,
        genre.id,
        sub.id,
        user_id=user.id,
        title=None,
        upload_status=UploadStatus.LOCAL,
    )

    assert first.id != second.id


@pytest.mark.asyncio
async def test_update_recording_lets_a_split_child_take_a_used_title(
    db_session: AsyncSession,
) -> None:
    """The unique index exempts split-derived rows, so the pre-check must exempt them on
    the way in as well — otherwise renaming one is a 409 for a title the database accepts."""
    rs = _import_service()
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre, sub = await make_oc_taxonomy(db_session)

    await make_oc_recording(
        db_session,
        project_id,
        genre.id,
        sub.id,
        user_id=user.id,
        title="Genesis 1",
        upload_status=UploadStatus.LOCAL,
    )
    split_child = OC_Recording(
        project_id=project_id,
        genre_id=genre.id,
        subcategory_id=sub.id,
        user_id=user.id,
        title="Genesis 1 part two",
        split_from_id="parent-id",
        duration_seconds=5.0,
        file_size_bytes=512,
        format="m4a",
        recorded_at=datetime.now(UTC),
    )
    db_session.add(split_child)
    await db_session.commit()
    await db_session.refresh(split_child)

    updated = await rs.update_recording(
        db_session, split_child.id, RecordingUpdate(title="Genesis 1")
    )

    assert updated.title == "Genesis 1"


@pytest.mark.asyncio
async def test_update_recording_lets_an_archived_split_parent_take_a_used_title(
    db_session: AsyncSession,
) -> None:
    """Same exemption, other half of the index predicate."""
    rs = _import_service()
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre, sub = await make_oc_taxonomy(db_session)

    await make_oc_recording(
        db_session,
        project_id,
        genre.id,
        sub.id,
        user_id=user.id,
        title="Genesis 1",
        upload_status=UploadStatus.LOCAL,
    )
    archived_parent = OC_Recording(
        project_id=project_id,
        genre_id=genre.id,
        subcategory_id=sub.id,
        user_id=user.id,
        title="Genesis 1 whole",
        splitting_status=SplittingStatus.ARCHIVED_AFTER_SPLIT,
        duration_seconds=5.0,
        file_size_bytes=512,
        format="m4a",
        recorded_at=datetime.now(UTC),
    )
    db_session.add(archived_parent)
    await db_session.commit()
    await db_session.refresh(archived_parent)

    updated = await rs.update_recording(
        db_session, archived_parent.id, RecordingUpdate(title="Genesis 1")
    )

    assert updated.title == "Genesis 1"


@pytest.mark.asyncio
async def test_create_recording_answers_422_for_a_genre_that_does_not_exist(
    db_session: AsyncSession,
) -> None:
    """The insert carries several foreign keys. A payload naming a row that is not there
    is the caller's mistake, not an internal fault, and only the title index may answer
    409."""
    rs = _import_service()
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    _, sub = await make_oc_taxonomy(db_session)

    data = RecordingCreate(
        description="a description long enough to satisfy the rule",
        project_id=project_id,
        genre_id="no-such-genre",
        subcategory_id=sub.id,
        title="Genesis 1",
        duration_seconds=10.0,
        file_size_bytes=1024,
        format="m4a",
        recorded_at=datetime.now(UTC),
    )

    with pytest.raises(UnknownReferenceError):
        await rs.create_recording(db_session, data, user.id)


@pytest.mark.asyncio
async def test_update_recording_answers_422_for_a_genre_that_does_not_exist(
    db_session: AsyncSession,
) -> None:
    rs = _import_service()
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre, sub = await make_oc_taxonomy(db_session)

    rec = await make_oc_recording(
        db_session, project_id, genre.id, sub.id, user_id=user.id, upload_status=UploadStatus.LOCAL
    )

    with pytest.raises(UnknownReferenceError):
        await rs.update_recording(db_session, rec.id, RecordingUpdate(genre_id="no-such-genre"))


def _postgres_fk_violation(constraint: str) -> IntegrityError:
    """A foreign key violation shaped the way asyncpg reports one.

    The suite runs on SQLite, which says only that some foreign key failed. Postgres
    names the constraint, and naming the offending field depends on reading it, so the
    message has to come from somewhere.
    """
    return IntegrityError(
        "INSERT INTO oc_recordings ...",
        {},
        Exception(
            'insert or update on table "oc_recordings" violates '
            f'foreign key constraint "{constraint}"'
        ),
    )


def test_a_violation_names_the_one_field_that_is_wrong() -> None:
    """Listing six ids and asking the caller which one they got wrong is work they
    cannot do: they hold every value and none of them looks different."""
    rs = _import_service()

    error = rs._unknown_reference_error(_postgres_fk_violation("oc_recordings_genre_id_fkey"))

    assert error is not None
    assert "genre_id" in str(error)
    assert "storyteller_id" not in str(error)


def test_a_secondary_field_is_not_reported_as_its_primary() -> None:
    """`oc_recordings_secondary_genre_id_fkey` contains `genre_id`, so a substring test
    would send the caller to a field that is fine."""
    rs = _import_service()

    error = rs._unknown_reference_error(
        _postgres_fk_violation("oc_recordings_secondary_genre_id_fkey")
    )

    assert error is not None
    assert "secondary_genre_id" in str(error)


def test_a_missing_account_is_not_the_callers_fault() -> None:
    """`user_id` comes from the authenticated token, never from the payload. A violation
    on it means the account behind a valid token is gone — answering 422 would tell the
    caller to fix ids that are all correct, and would hide a real fault behind a 4xx that
    pages nobody."""
    rs = _import_service()

    assert rs._unknown_reference_error(_postgres_fk_violation("oc_recordings_user_id_fkey")) is None


def test_a_database_that_names_nothing_still_answers_the_caller() -> None:
    """SQLite reports only that some foreign key failed. The full list is the honest
    answer there — a wrong single field would be worse than an unspecific one."""
    rs = _import_service()

    error = rs._unknown_reference_error(
        IntegrityError(
            "INSERT INTO oc_recordings ...", {}, Exception("FOREIGN KEY constraint failed")
        )
    )

    assert error is not None
    assert "project_id" in str(error)
    assert "storyteller_id" in str(error)


def test_a_conflict_that_is_not_a_foreign_key_is_left_alone() -> None:
    rs = _import_service()

    assert (
        rs._unknown_reference_error(
            IntegrityError(
                "INSERT ...", {}, Exception("duplicate key value violates unique constraint")
            )
        )
        is None
    )


@pytest.mark.asyncio
async def test_unknown_reference_is_served_as_422() -> None:
    """422 rather than 400: the payload parsed fine and every field is well formed, it
    just names a row that is not there. That is the same class of problem FastAPI already
    answers 422 for, and it is the caller's to fix — a 500 would claim otherwise."""
    import httpx
    from fastapi import FastAPI
    from httpx import ASGITransport

    from app.core.exceptions import register_exception_handlers

    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    async def _boom() -> None:
        raise UnknownReferenceError("no such genre")

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/boom")

    assert response.status_code == 422
    assert response.json()["detail"] == "no such genre"
