import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import UploadStatus
from app.core.exceptions import AuthorizationError
from app.db.models.oc_recording import OC_Recording
from app.db.models.project import ProjectUserAccess
from tests.baker import (
    make_language,
    make_oc_recording,
    make_oc_taxonomy,
    make_project,
    make_user,
)

pytest.importorskip("app.inngest")


def _import_service():
    from app.services.oral_collector import recording_service

    return recording_service


async def _seed_project_with_manager(
    db: AsyncSession,
    *,
    email: str = "manager@test.com",
    name: str = "Test Project",
    language_code: str = "tst",
) -> tuple[str, str]:
    lang = await make_language(db, code=language_code, name=name)
    project = await make_project(db, lang.id, name=name)
    manager = await make_user(db, email=email)
    db.add(ProjectUserAccess(project_id=project.id, user_id=manager.id, role="manager"))
    await db.commit()
    return project.id, manager.id


async def _surviving_ids(db: AsyncSession) -> set[str]:
    result = await db.execute(select(OC_Recording.id))
    return set(result.scalars().all())


@pytest.mark.asyncio
async def test_clearing_stale_recordings_deletes_a_failed_upload_but_spares_one_in_flight(
    db_session: AsyncSession,
) -> None:
    rs = _import_service()
    project_id, manager_id = await _seed_project_with_manager(db_session)
    genre, sub = await make_oc_taxonomy(db_session)

    in_flight = await make_oc_recording(
        db_session,
        project_id,
        genre.id,
        sub.id,
        user_id=manager_id,
        upload_status=UploadStatus.UPLOADING,
        title="still uploading",
    )
    await make_oc_recording(
        db_session,
        project_id,
        genre.id,
        sub.id,
        user_id=manager_id,
        upload_status=UploadStatus.UPLOAD_FAILED,
        title="upload failed",
    )

    deleted = await rs.clear_stale_recordings(db_session, project_id, manager_id)

    assert deleted == 1
    assert await _surviving_ids(db_session) == {in_flight.id}


@pytest.mark.asyncio
async def test_clearing_stale_recordings_reports_the_number_of_rows_it_removed(
    db_session: AsyncSession,
) -> None:
    rs = _import_service()
    project_id, manager_id = await _seed_project_with_manager(db_session)
    genre, sub = await make_oc_taxonomy(db_session)

    for index in range(3):
        await make_oc_recording(
            db_session,
            project_id,
            genre.id,
            sub.id,
            user_id=manager_id,
            upload_status=UploadStatus.UPLOAD_FAILED,
            title=f"upload failed {index}",
        )

    deleted = await rs.clear_stale_recordings(db_session, project_id, manager_id)

    assert deleted == 3
    assert await _surviving_ids(db_session) == set()


@pytest.mark.asyncio
async def test_clearing_stale_recordings_leaves_local_uploaded_and_verified_recordings_alone(
    db_session: AsyncSession,
) -> None:
    rs = _import_service()
    project_id, manager_id = await _seed_project_with_manager(db_session)
    genre, sub = await make_oc_taxonomy(db_session)

    kept = set()
    for status in (UploadStatus.LOCAL, UploadStatus.UPLOADED, UploadStatus.VERIFIED):
        recording = await make_oc_recording(
            db_session,
            project_id,
            genre.id,
            sub.id,
            user_id=manager_id,
            upload_status=status,
            title=f"recording {status}",
        )
        kept.add(recording.id)

    deleted = await rs.clear_stale_recordings(db_session, project_id, manager_id)

    assert deleted == 0
    assert await _surviving_ids(db_session) == kept


@pytest.mark.asyncio
async def test_clearing_stale_recordings_deletes_the_bucket_blob_only_of_a_row_that_has_one(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    rs = _import_service()
    project_id, manager_id = await _seed_project_with_manager(db_session)
    genre, sub = await make_oc_taxonomy(db_session)

    deleted_blobs: list[str] = []
    monkeypatch.setattr(rs, "_delete_gcs_blob", deleted_blobs.append)

    blob_url = f"{rs.GCS_PUBLIC_BASE}oral-collector/{project_id}/{genre.id}/in-bucket.m4a"
    await make_oc_recording(
        db_session,
        project_id,
        genre.id,
        sub.id,
        user_id=manager_id,
        upload_status=UploadStatus.UPLOAD_FAILED,
        gcs_url=blob_url,
        title="failed after reaching the bucket",
    )
    await make_oc_recording(
        db_session,
        project_id,
        genre.id,
        sub.id,
        user_id=manager_id,
        upload_status=UploadStatus.UPLOAD_FAILED,
        title="failed before reaching the bucket",
    )

    deleted = await rs.clear_stale_recordings(db_session, project_id, manager_id)

    assert deleted == 2
    assert deleted_blobs == [blob_url]


@pytest.mark.asyncio
async def test_clearing_stale_recordings_is_refused_to_a_non_manager_and_deletes_nothing(
    db_session: AsyncSession,
) -> None:
    rs = _import_service()
    project_id, _manager_id = await _seed_project_with_manager(db_session)
    member = await make_user(db_session, email="member@test.com")
    db_session.add(ProjectUserAccess(project_id=project_id, user_id=member.id, role="member"))
    await db_session.commit()
    genre, sub = await make_oc_taxonomy(db_session)

    failed = await make_oc_recording(
        db_session,
        project_id,
        genre.id,
        sub.id,
        user_id=member.id,
        upload_status=UploadStatus.UPLOAD_FAILED,
        title="upload failed",
    )

    with pytest.raises(AuthorizationError):
        await rs.clear_stale_recordings(db_session, project_id, member.id)

    assert await _surviving_ids(db_session) == {failed.id}


@pytest.mark.asyncio
async def test_clearing_stale_recordings_leaves_another_projects_recordings_alone(
    db_session: AsyncSession,
) -> None:
    rs = _import_service()
    project_id, manager_id = await _seed_project_with_manager(db_session)
    other_project_id, _other_manager_id = await _seed_project_with_manager(
        db_session, email="other-manager@test.com", name="Other Project", language_code="oth"
    )
    genre, sub = await make_oc_taxonomy(db_session)

    await make_oc_recording(
        db_session,
        project_id,
        genre.id,
        sub.id,
        user_id=manager_id,
        upload_status=UploadStatus.UPLOAD_FAILED,
        title="upload failed",
    )
    other_failed = await make_oc_recording(
        db_session,
        other_project_id,
        genre.id,
        sub.id,
        user_id=manager_id,
        upload_status=UploadStatus.UPLOAD_FAILED,
        title="upload failed",
    )

    deleted = await rs.clear_stale_recordings(db_session, project_id, manager_id)

    assert deleted == 1
    assert await _surviving_ids(db_session) == {other_failed.id}
