from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import CleaningStatus, SplittingStatus, UploadStatus
from app.db.models.oc_recording import OC_Recording
from app.inngest.audio_splitting import persist_split_segments
from app.inngest.schemas import SegmentResult, SplitRequestedPayload, SplitSegmentData
from app.models.oc_recording import RecordingCreate, RecordingResponse, RecordingUpdate
from app.services.oral_collector.recording_service import list_recordings
from app.services.oral_collector.split_service import backfill_split_indices, get_split_status
from tests.baker import (
    make_language,
    make_oc_recording,
    make_oc_taxonomy,
    make_project,
    make_user,
)

pytest.importorskip("app.inngest")


async def _seed_project(db: AsyncSession) -> str:
    lang = await make_language(db)
    project = await make_project(db, lang.id)
    return project.id


async def _seed_parent(
    db: AsyncSession,
    *,
    user_id: str,
    project_id: str,
    genre_id: str,
    subcategory_id: str,
    gcs_url: str = "https://example.com/parent.m4a",
) -> OC_Recording:
    """A recording mid-split: verified, sitting in GCS, already marked `splitting`."""
    return await make_oc_recording(
        db,
        project_id,
        genre_id,
        subcategory_id,
        user_id=user_id,
        title="Parent story",
        duration_seconds=60.0,
        file_size_bytes=100_000,
        gcs_url=gcs_url,
        upload_status=UploadStatus.VERIFIED,
        splitting_status=SplittingStatus.SPLITTING,
    )


def _make_payload(
    *,
    recording_id: str,
    user_id: str,
    project_id: str,
    genre_id: str,
    subcategory_id: str,
    segment_count: int,
) -> SplitRequestedPayload:
    return SplitRequestedPayload(
        recording_id=recording_id,
        user_id=user_id,
        segments=[
            SplitSegmentData(
                start_seconds=float(i) * 10.0,
                end_seconds=float(i + 1) * 10.0,
                genre_id=genre_id,
                subcategory_id=subcategory_id,
            )
            for i in range(segment_count)
        ],
        project_id=project_id,
        format="m4a",
        title="Parent story",
        recorded_at=datetime.now(UTC).isoformat(),
    )


def _make_segment_results(count: int) -> list[SegmentResult]:
    return [
        SegmentResult(
            id=f"child-{i}",
            gcs_url=f"https://example.com/child-{i}.m4a",
            duration_seconds=10.0,
            file_size_bytes=10_000,
            index=i,
        )
        for i in range(count)
    ]


@pytest.mark.asyncio
async def test_persist_split_segments_sets_lineage_on_every_child(
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre, sub = await make_oc_taxonomy(db_session)
    parent = await _seed_parent(
        db_session,
        user_id=user.id,
        project_id=project_id,
        genre_id=genre.id,
        subcategory_id=sub.id,
    )
    payload = _make_payload(
        recording_id=parent.id,
        user_id=user.id,
        project_id=project_id,
        genre_id=genre.id,
        subcategory_id=sub.id,
        segment_count=3,
    )

    new_ids = await persist_split_segments(db_session, payload, _make_segment_results(3))

    assert new_ids == ["child-0", "child-1", "child-2"]

    for i, new_id in enumerate(new_ids):
        child = await db_session.get(OC_Recording, new_id)
        assert child is not None
        assert child.split_from_id == parent.id
        assert child.split_index == i
        assert child.split_segment_count == 3
        assert child.upload_status == UploadStatus.VERIFIED


@pytest.mark.asyncio
async def test_persist_split_segments_archives_parent_instead_of_deleting(
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre, sub = await make_oc_taxonomy(db_session)
    parent = await _seed_parent(
        db_session,
        user_id=user.id,
        project_id=project_id,
        genre_id=genre.id,
        subcategory_id=sub.id,
    )
    payload = _make_payload(
        recording_id=parent.id,
        user_id=user.id,
        project_id=project_id,
        genre_id=genre.id,
        subcategory_id=sub.id,
        segment_count=2,
    )

    await persist_split_segments(db_session, payload, _make_segment_results(2))

    refreshed = await db_session.get(OC_Recording, parent.id)
    assert refreshed is not None, "parent row must survive the split"
    assert refreshed.splitting_status == SplittingStatus.ARCHIVED_AFTER_SPLIT


@pytest.mark.asyncio
async def test_list_recordings_excludes_archived_parents(
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre, sub = await make_oc_taxonomy(db_session)

    archived = await _seed_parent(
        db_session,
        user_id=user.id,
        project_id=project_id,
        genre_id=genre.id,
        subcategory_id=sub.id,
    )
    archived.splitting_status = SplittingStatus.ARCHIVED_AFTER_SPLIT
    active = await _seed_parent(
        db_session,
        user_id=user.id,
        project_id=project_id,
        genre_id=genre.id,
        subcategory_id=sub.id,
    )
    active.splitting_status = SplittingStatus.NONE
    await db_session.commit()

    results = await list_recordings(db_session, project_id)
    ids = {r.id for r in results}
    assert active.id in ids
    assert archived.id not in ids


@pytest.mark.asyncio
async def test_get_split_status_orders_children_by_split_index(
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre, sub = await make_oc_taxonomy(db_session)
    parent = await _seed_parent(
        db_session,
        user_id=user.id,
        project_id=project_id,
        genre_id=genre.id,
        subcategory_id=sub.id,
    )
    parent.splitting_status = SplittingStatus.ARCHIVED_AFTER_SPLIT
    await db_session.commit()

    base_time = datetime.now(UTC)
    children_out_of_order = [
        ("c-2", 2, base_time),
        ("c-0", 0, base_time + timedelta(seconds=1)),
        ("c-1", 1, base_time + timedelta(seconds=2)),
    ]
    for cid, idx, created in children_out_of_order:
        child = OC_Recording(
            id=cid,
            project_id=project_id,
            genre_id=genre.id,
            subcategory_id=sub.id,
            user_id=user.id,
            title=f"child {idx}",
            duration_seconds=10.0,
            file_size_bytes=1_000,
            format="m4a",
            upload_status=UploadStatus.VERIFIED,
            cleaning_status=CleaningStatus.NONE,
            splitting_status=SplittingStatus.NONE,
            split_from_id=parent.id,
            split_index=idx,
            split_segment_count=3,
            recorded_at=base_time,
            created_at=created,
        )
        db_session.add(child)
    await db_session.commit()

    _, segment_ids = await get_split_status(db_session, parent.id)
    assert segment_ids == ["c-0", "c-1", "c-2"]


@pytest.mark.asyncio
async def test_get_split_status_falls_back_to_created_at_for_legacy_rows(
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre, sub = await make_oc_taxonomy(db_session)
    parent = await _seed_parent(
        db_session,
        user_id=user.id,
        project_id=project_id,
        genre_id=genre.id,
        subcategory_id=sub.id,
    )
    parent.splitting_status = SplittingStatus.COMPLETED
    await db_session.commit()

    base_time = datetime.now(UTC)
    legacy_children = [
        ("legacy-b", base_time + timedelta(seconds=2)),
        ("legacy-a", base_time + timedelta(seconds=1)),
        ("legacy-c", base_time + timedelta(seconds=3)),
    ]
    for cid, created in legacy_children:
        db_session.add(
            OC_Recording(
                id=cid,
                project_id=project_id,
                genre_id=genre.id,
                subcategory_id=sub.id,
                user_id=user.id,
                title=cid,
                duration_seconds=10.0,
                file_size_bytes=1_000,
                format="m4a",
                upload_status=UploadStatus.VERIFIED,
                cleaning_status=CleaningStatus.NONE,
                splitting_status=SplittingStatus.NONE,
                split_from_id=parent.id,
                recorded_at=base_time,
                created_at=created,
            )
        )
    await db_session.commit()

    _, segment_ids = await get_split_status(db_session, parent.id)
    assert segment_ids == ["legacy-a", "legacy-b", "legacy-c"]


@pytest.mark.asyncio
async def test_get_split_status_empty_when_not_split(
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre, sub = await make_oc_taxonomy(db_session)
    parent = await _seed_parent(
        db_session,
        user_id=user.id,
        project_id=project_id,
        genre_id=genre.id,
        subcategory_id=sub.id,
    )
    parent.splitting_status = SplittingStatus.NONE
    await db_session.commit()

    _, segment_ids = await get_split_status(db_session, parent.id)
    assert segment_ids == []


def test_recording_response_serializes_split_lineage_fields() -> None:
    resp = RecordingResponse(
        id="rec-1",
        project_id="proj-1",
        genre_id="g1",
        subcategory_id="s1",
        title="x",
        duration_seconds=1.0,
        file_size_bytes=1,
        format="m4a",
        gcs_url=None,
        upload_status=UploadStatus.VERIFIED,
        cleaning_status=CleaningStatus.NONE,
        splitting_status=SplittingStatus.NONE,
        split_from_id="parent-1",
        split_index=0,
        split_segment_count=3,
        recorded_at=datetime.now(UTC),
        uploaded_at=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    dumped = resp.model_dump()
    assert dumped["split_from_id"] == "parent-1"
    assert dumped["split_index"] == 0
    assert dumped["split_segment_count"] == 3


def test_recording_create_rejects_split_lineage_fields() -> None:
    payload = RecordingCreate.model_validate(
        {
            "project_id": "p",
            "genre_id": "g",
            "subcategory_id": "s",
            "description": "a description long enough to satisfy the rule",
            "duration_seconds": 1.0,
            "file_size_bytes": 1,
            "format": "m4a",
            "recorded_at": datetime.now(UTC).isoformat(),
            "split_from_id": "parent-x",
            "split_index": 9,
            "split_segment_count": 99,
        }
    )
    dumped = payload.model_dump()
    assert "split_from_id" not in dumped
    assert "split_index" not in dumped
    assert "split_segment_count" not in dumped


def test_recording_update_rejects_split_lineage_fields() -> None:
    payload = RecordingUpdate.model_validate(
        {
            "title": "new",
            "split_from_id": "other-parent",
            "split_index": 42,
            "split_segment_count": 7,
        }
    )
    dumped = payload.model_dump(exclude_unset=True)
    assert dumped == {"title": "new"}


@pytest.mark.asyncio
async def test_backfill_populates_legacy_split_groups(
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre, sub = await make_oc_taxonomy(db_session)

    base_time = datetime.now(UTC)
    parent_a = "parent-A"
    parent_b = "parent-B"
    seed = [
        ("a2", parent_a, base_time + timedelta(seconds=3)),
        ("a0", parent_a, base_time + timedelta(seconds=1)),
        ("a1", parent_a, base_time + timedelta(seconds=2)),
        ("b0", parent_b, base_time + timedelta(seconds=10)),
        ("b1", parent_b, base_time + timedelta(seconds=11)),
    ]
    for cid, parent_id, created in seed:
        db_session.add(
            OC_Recording(
                id=cid,
                project_id=project_id,
                genre_id=genre.id,
                subcategory_id=sub.id,
                user_id=user.id,
                title=cid,
                duration_seconds=10.0,
                file_size_bytes=1_000,
                format="m4a",
                upload_status=UploadStatus.VERIFIED,
                cleaning_status=CleaningStatus.NONE,
                splitting_status=SplittingStatus.NONE,
                split_from_id=parent_id,
                recorded_at=base_time,
                created_at=created,
            )
        )
    await db_session.commit()

    total_updated, total_groups = await backfill_split_indices(db_session)
    assert total_groups == 2
    assert total_updated == 5

    rows = {
        r.id: (r.split_index, r.split_segment_count)
        for r in (await db_session.execute(select(OC_Recording))).scalars().all()
    }
    assert rows["a0"] == (0, 3)
    assert rows["a1"] == (1, 3)
    assert rows["a2"] == (2, 3)
    assert rows["b0"] == (0, 2)
    assert rows["b1"] == (1, 2)


@pytest.mark.asyncio
async def test_backfill_is_idempotent(db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre, sub = await make_oc_taxonomy(db_session)

    base_time = datetime.now(UTC)
    db_session.add(
        OC_Recording(
            id="only-child",
            project_id=project_id,
            genre_id=genre.id,
            subcategory_id=sub.id,
            user_id=user.id,
            title="x",
            duration_seconds=10.0,
            file_size_bytes=1_000,
            format="m4a",
            upload_status=UploadStatus.VERIFIED,
            cleaning_status=CleaningStatus.NONE,
            splitting_status=SplittingStatus.NONE,
            split_from_id="some-parent",
            recorded_at=base_time,
            created_at=base_time,
        )
    )
    await db_session.commit()

    first_updated, first_groups = await backfill_split_indices(db_session)
    assert first_updated == 1
    assert first_groups == 1

    second_updated, second_groups = await backfill_split_indices(db_session)
    assert second_updated == 0
    assert second_groups == 0


@pytest.mark.asyncio
async def test_backfill_ignores_non_split_rows(db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre, sub = await make_oc_taxonomy(db_session)

    base_time = datetime.now(UTC)
    db_session.add(
        OC_Recording(
            id="standalone",
            project_id=project_id,
            genre_id=genre.id,
            subcategory_id=sub.id,
            user_id=user.id,
            title="standalone",
            duration_seconds=10.0,
            file_size_bytes=1_000,
            format="m4a",
            upload_status=UploadStatus.VERIFIED,
            cleaning_status=CleaningStatus.NONE,
            splitting_status=SplittingStatus.NONE,
            split_from_id=None,
            recorded_at=base_time,
            created_at=base_time,
        )
    )
    await db_session.commit()

    total_updated, total_groups = await backfill_split_indices(db_session)
    assert total_updated == 0
    assert total_groups == 0

    row = await db_session.get(OC_Recording, "standalone")
    assert row is not None
    assert row.split_index is None
    assert row.split_segment_count is None
