from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import CleaningStatus, UploadStatus
from app.core.exceptions import (
    AuthorizationError,
    InvalidCleaningStatusError,
    NotFoundError,
    SecondaryClassificationConflictError,
    ValidationError,
)
from app.db.models.oc_genre import OC_Genre, OC_Subcategory
from app.db.models.oc_recording import OC_Recording
from app.db.models.oc_storyteller import OC_Storyteller
from app.db.models.project import ProjectUserAccess
from app.models.oc_recording import (
    ConfirmUploadRequest,
    RecordingCreate,
    RecordingUpdate,
    ResumableUploadUrlRequest,
    ResumableUploadUrlResponse,
)
from tests.baker import make_language, make_project, make_user

pytest.importorskip("app.inngest")


async def _seed_genre(db: AsyncSession) -> tuple[OC_Genre, OC_Subcategory]:
    genre = OC_Genre(name="narrative", sort_order=0)
    db.add(genre)
    await db.flush()

    sub = OC_Subcategory(genre_id=genre.id, name="folktale", sort_order=0)
    db.add(sub)
    await db.commit()
    await db.refresh(genre)
    await db.refresh(sub)
    return genre, sub


async def _seed_project(db: AsyncSession) -> str:
    lang = await make_language(db)
    project = await make_project(db, lang.id)
    return project.id


async def _seed_recording(
    db: AsyncSession,
    user_id: str,
    project_id: str,
    genre_id: str,
    subcategory_id: str,
    *,
    upload_status: str = UploadStatus.LOCAL,
    file_size_bytes: int = 1024,
) -> OC_Recording:
    rec = OC_Recording(
        project_id=project_id,
        genre_id=genre_id,
        subcategory_id=subcategory_id,
        user_id=user_id,
        title="test recording",
        duration_seconds=10.0,
        file_size_bytes=file_size_bytes,
        format="m4a",
        upload_status=upload_status,
        recorded_at=datetime.now(UTC),
    )
    db.add(rec)
    await db.commit()
    await db.refresh(rec)
    return rec


def _import_service():
    from app.services.oral_collector import recording_service

    return recording_service


@pytest.mark.asyncio
async def test_create_recording(db_session: AsyncSession) -> None:
    rs = _import_service()
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre, sub = await _seed_genre(db_session)

    data = RecordingCreate(
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
    genre, sub = await _seed_genre(db_session)

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
    genre, sub = await _seed_genre(db_session)
    rec = await _seed_recording(db_session, user.id, project_id, genre.id, sub.id)

    updated = await rs.update_recording(
        db_session, rec.id, RecordingUpdate(description="A new story")
    )
    assert updated.description == "A new story"

    cleared = await rs.update_recording(db_session, rec.id, RecordingUpdate(description=None))
    assert cleared.description is None


@pytest.mark.asyncio
async def test_update_recording_sets_cleaning_status(db_session: AsyncSession) -> None:
    rs = _import_service()
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre, sub = await _seed_genre(db_session)
    rec = await _seed_recording(db_session, user.id, project_id, genre.id, sub.id)
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
    genre, sub = await _seed_genre(db_session)
    rec = await _seed_recording(db_session, user.id, project_id, genre.id, sub.id)

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
    genre, sub = await _seed_genre(db_session)

    rec = await _seed_recording(db_session, user.id, project_id, genre.id, sub.id)
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
    genre, sub = await _seed_genre(db_session)

    rec = await _seed_recording(db_session, user.id, project_id, genre.id, sub.id)
    updated = await rs.update_recording(db_session, rec.id, RecordingUpdate(title="Updated Title"))

    assert updated.title == "Updated Title"


@pytest.mark.asyncio
async def test_delete_recording(db_session: AsyncSession) -> None:
    rs = _import_service()
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre, sub = await _seed_genre(db_session)

    rec = await _seed_recording(db_session, user.id, project_id, genre.id, sub.id)
    await rs.delete_recording(db_session, rec.id)

    with pytest.raises(NotFoundError):
        await rs.get_recording(db_session, rec.id)


@pytest.mark.asyncio
async def test_list_recordings(db_session: AsyncSession) -> None:
    rs = _import_service()
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre, sub = await _seed_genre(db_session)

    await _seed_recording(
        db_session,
        user.id,
        project_id,
        genre.id,
        sub.id,
        upload_status=UploadStatus.UPLOADED,
    )
    await _seed_recording(
        db_session,
        user.id,
        project_id,
        genre.id,
        sub.id,
        upload_status=UploadStatus.VERIFIED,
    )

    recordings = await rs.list_recordings(db_session, project_id)
    assert len(recordings) == 2


@pytest.mark.asyncio
async def test_list_recordings_filter_by_status(db_session: AsyncSession) -> None:
    rs = _import_service()
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre, sub = await _seed_genre(db_session)

    await _seed_recording(
        db_session,
        user.id,
        project_id,
        genre.id,
        sub.id,
        upload_status=UploadStatus.UPLOADED,
    )
    await _seed_recording(
        db_session,
        user.id,
        project_id,
        genre.id,
        sub.id,
        upload_status=UploadStatus.LOCAL,
    )

    uploaded = await rs.list_recordings(db_session, project_id, upload_status=UploadStatus.UPLOADED)
    assert len(uploaded) == 1
    assert uploaded[0].upload_status == UploadStatus.UPLOADED


@pytest.mark.asyncio
async def test_check_recording_access_owner(db_session: AsyncSession) -> None:
    rs = _import_service()
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre, sub = await _seed_genre(db_session)

    rec = await _seed_recording(db_session, user.id, project_id, genre.id, sub.id)
    await rs.check_recording_access(db_session, rec, user.id)


@pytest.mark.asyncio
async def test_check_recording_access_denied(db_session: AsyncSession) -> None:
    rs = _import_service()
    user = await make_user(db_session, email="owner@test.com")
    other = await make_user(db_session, email="other@test.com")
    project_id = await _seed_project(db_session)
    genre, sub = await _seed_genre(db_session)

    rec = await _seed_recording(db_session, user.id, project_id, genre.id, sub.id)
    with pytest.raises(AuthorizationError):
        await rs.check_recording_access(db_session, rec, other.id)


@pytest.mark.asyncio
async def test_check_recording_access_manager(db_session: AsyncSession) -> None:
    rs = _import_service()
    user = await make_user(db_session, email="owner@test.com")
    manager = await make_user(db_session, email="manager@test.com")
    project_id = await _seed_project(db_session)
    genre, sub = await _seed_genre(db_session)

    access = ProjectUserAccess(project_id=project_id, user_id=manager.id, role="manager")
    db_session.add(access)
    await db_session.commit()

    rec = await _seed_recording(db_session, user.id, project_id, genre.id, sub.id)
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


async def _seed_storyteller(db: AsyncSession, project_id: str, name: str = "Ana") -> OC_Storyteller:
    st = OC_Storyteller(
        project_id=project_id,
        name=name,
        sex="female",
        external_acceptance_confirmed=True,
    )
    db.add(st)
    await db.commit()
    await db.refresh(st)
    return st


@pytest.mark.asyncio
async def test_create_recording_with_storyteller(db_session: AsyncSession) -> None:
    rs = _import_service()
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre, sub = await _seed_genre(db_session)
    storyteller = await _seed_storyteller(db_session, project_id)

    data = RecordingCreate(
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
    storyteller_b = await _seed_storyteller(db_session, project_b.id)

    genre, sub = await _seed_genre(db_session)
    data = RecordingCreate(
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
    genre, sub = await _seed_genre(db_session)
    rec = await _seed_recording(db_session, user.id, project_id_a, genre.id, sub.id)

    lang_b = await make_language(db_session, name="Other", code="oth")
    from tests.baker import make_project as _make_project

    project_b = await _make_project(db_session, lang_b.id, name="Other Project")
    storyteller_b = await _seed_storyteller(db_session, project_b.id)

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
    genre, sub = await _seed_genre(db_session)

    genre_b = OC_Genre(name="wisdom", sort_order=1)
    db_session.add(genre_b)
    await db_session.flush()
    sub_b = OC_Subcategory(genre_id=genre_b.id, name="proverb", sort_order=0)
    db_session.add(sub_b)
    await db_session.commit()
    await db_session.refresh(genre_b)
    await db_session.refresh(sub_b)

    data = RecordingCreate(
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
    genre, sub = await _seed_genre(db_session)

    other_sub = OC_Subcategory(genre_id=genre.id, name="other", sort_order=1)
    db_session.add(other_sub)
    await db_session.commit()
    await db_session.refresh(other_sub)

    data = RecordingCreate(
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
    genre, sub = await _seed_genre(db_session)

    data = RecordingCreate(
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
    genre, sub = await _seed_genre(db_session)
    rec = await _seed_recording(db_session, user.id, project_id, genre.id, sub.id)
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
    genre, sub = await _seed_genre(db_session)
    rec = await _seed_recording(db_session, user.id, project_id, genre.id, sub.id)
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
    genre, sub = await _seed_genre(db_session)
    rec = await _seed_recording(db_session, user.id, project_id, genre.id, sub.id)
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
    genre, sub = await _seed_genre(db_session)
    rec = await _seed_recording(db_session, user.id, project_id, genre.id, sub.id)
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
    genre, sub = await _seed_genre(db_session)
    st_a = await _seed_storyteller(db_session, project_id, name="Ana")
    st_b = await _seed_storyteller(db_session, project_id, name="Beto")

    rec_a = await _seed_recording(
        db_session,
        user_a.id,
        project_id,
        genre.id,
        sub.id,
        upload_status=UploadStatus.UPLOADED,
    )
    rec_b = await _seed_recording(
        db_session,
        user_b.id,
        project_id,
        genre.id,
        sub.id,
        upload_status=UploadStatus.UPLOADED,
    )
    rec_a.storyteller_id = st_a.id
    rec_b.storyteller_id = st_b.id
    await db_session.commit()

    by_user = await rs.list_recordings(db_session, project_id, user_id=user_a.id)
    assert {r.id for r in by_user} == {rec_a.id}

    by_st = await rs.list_recordings(db_session, project_id, storyteller_id=st_b.id)
    assert {r.id for r in by_st} == {rec_b.id}
