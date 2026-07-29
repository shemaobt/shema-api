"""Tests for parent → child metadata propagation in the /split flow (ENG-64)."""

from datetime import UTC, datetime

import inngest
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import CleaningStatus, OCRecordingEvent, SplittingStatus, UploadStatus
from app.db.models.oc_genre import OC_Genre, OC_Subcategory
from app.db.models.oc_recording import OC_Recording
from app.db.models.oc_storyteller import OC_Storyteller
from app.inngest.audio_splitting import persist_split_segments
from app.inngest.schemas import SegmentResult, SplitRequestedPayload, SplitSegmentData
from app.models.oc_recording import SplitSegment
from app.services.oral_collector import split_service
from app.services.oral_collector.split_service import request_split
from tests.baker import make_language, make_project, make_user

pytest.importorskip("app.inngest")


async def _seed_two_genres(
    db: AsyncSession,
) -> tuple[OC_Genre, OC_Subcategory, OC_Genre, OC_Subcategory]:
    primary_genre = OC_Genre(name="narrative", sort_order=0)
    secondary_genre = OC_Genre(name="proverb", sort_order=1)
    db.add_all([primary_genre, secondary_genre])
    await db.flush()
    primary_sub = OC_Subcategory(genre_id=primary_genre.id, name="folktale", sort_order=0)
    secondary_sub = OC_Subcategory(genre_id=secondary_genre.id, name="riddle", sort_order=0)
    db.add_all([primary_sub, secondary_sub])
    await db.commit()
    for obj in (primary_genre, primary_sub, secondary_genre, secondary_sub):
        await db.refresh(obj)
    return primary_genre, primary_sub, secondary_genre, secondary_sub


async def _seed_storyteller(db: AsyncSession, project_id: str) -> OC_Storyteller:
    storyteller = OC_Storyteller(project_id=project_id, name="Maria", sex="female", age=70)
    db.add(storyteller)
    await db.commit()
    await db.refresh(storyteller)
    return storyteller


async def _seed_parent_with_full_metadata(
    db: AsyncSession,
    *,
    user_id: str,
    project_id: str,
    primary_genre_id: str,
    primary_subcategory_id: str,
    primary_register_id: str,
    secondary_genre_id: str,
    secondary_subcategory_id: str,
    secondary_register_id: str,
    storyteller_id: str,
    description: str = "An old story about the river",
    cleaning_status: str = CleaningStatus.CLEANED,
) -> OC_Recording:
    parent = OC_Recording(
        project_id=project_id,
        genre_id=primary_genre_id,
        subcategory_id=primary_subcategory_id,
        register_id=primary_register_id,
        secondary_genre_id=secondary_genre_id,
        secondary_subcategory_id=secondary_subcategory_id,
        secondary_register_id=secondary_register_id,
        user_id=user_id,
        storyteller_id=storyteller_id,
        title="Parent story",
        description=description,
        duration_seconds=60.0,
        file_size_bytes=100_000,
        format="m4a",
        gcs_url="https://example.com/parent.m4a",
        upload_status=UploadStatus.VERIFIED,
        cleaning_status=cleaning_status,
        splitting_status=SplittingStatus.SPLITTING,
        recorded_at=datetime.now(UTC),
    )
    db.add(parent)
    await db.commit()
    await db.refresh(parent)
    return parent


def _payload_with_inheritance(
    *,
    recording_id: str,
    user_id: str,
    project_id: str,
    primary_genre_id: str,
    primary_subcategory_id: str,
    primary_register_id: str | None,
    secondary_genre_id: str | None,
    secondary_subcategory_id: str | None,
    secondary_register_id: str | None,
    storyteller_id: str | None,
    description: str | None,
    segment_count: int,
) -> SplitRequestedPayload:
    return SplitRequestedPayload(
        recording_id=recording_id,
        user_id=user_id,
        segments=[
            SplitSegmentData(
                start_seconds=float(i) * 10.0,
                end_seconds=float(i + 1) * 10.0,
                genre_id=primary_genre_id,
                subcategory_id=primary_subcategory_id,
                register_id=primary_register_id,
            )
            for i in range(segment_count)
        ],
        project_id=project_id,
        format="m4a",
        title="Parent story",
        recorded_at=datetime.now(UTC).isoformat(),
        description=description,
        storyteller_id=storyteller_id,
        secondary_genre_id=secondary_genre_id,
        secondary_subcategory_id=secondary_subcategory_id,
        secondary_register_id=secondary_register_id,
    )


def _segment_results(count: int) -> list[SegmentResult]:
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
async def test_persist_split_segments_propagates_inherited_metadata_to_every_child(
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)
    pg, ps, sg, ss = await _seed_two_genres(db_session)
    storyteller = await _seed_storyteller(db_session, project.id)
    parent = await _seed_parent_with_full_metadata(
        db_session,
        user_id=user.id,
        project_id=project.id,
        primary_genre_id=pg.id,
        primary_subcategory_id=ps.id,
        primary_register_id="formal",
        secondary_genre_id=sg.id,
        secondary_subcategory_id=ss.id,
        secondary_register_id="casual",
        storyteller_id=storyteller.id,
        description="An old story about the river",
    )
    payload = _payload_with_inheritance(
        recording_id=parent.id,
        user_id=user.id,
        project_id=project.id,
        primary_genre_id=pg.id,
        primary_subcategory_id=ps.id,
        primary_register_id="formal",
        secondary_genre_id=sg.id,
        secondary_subcategory_id=ss.id,
        secondary_register_id="casual",
        storyteller_id=storyteller.id,
        description="An old story about the river",
        segment_count=3,
    )

    new_ids = await persist_split_segments(db_session, payload, _segment_results(3))

    assert new_ids == ["child-0", "child-1", "child-2"]
    for new_id in new_ids:
        child = await db_session.get(OC_Recording, new_id)
        assert child is not None, f"child {new_id} should exist"
        assert child.description == "An old story about the river"
        assert child.storyteller_id == storyteller.id
        assert child.user_id == user.id
        assert child.secondary_genre_id == sg.id
        assert child.secondary_subcategory_id == ss.id
        assert child.secondary_register_id == "casual"


@pytest.mark.asyncio
async def test_persist_split_segments_resets_cleaning_status_to_none_on_every_child(
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)
    pg, ps, sg, ss = await _seed_two_genres(db_session)
    storyteller = await _seed_storyteller(db_session, project.id)
    parent = await _seed_parent_with_full_metadata(
        db_session,
        user_id=user.id,
        project_id=project.id,
        primary_genre_id=pg.id,
        primary_subcategory_id=ps.id,
        primary_register_id="formal",
        secondary_genre_id=sg.id,
        secondary_subcategory_id=ss.id,
        secondary_register_id="casual",
        storyteller_id=storyteller.id,
        cleaning_status=CleaningStatus.CLEANED,
    )
    payload = _payload_with_inheritance(
        recording_id=parent.id,
        user_id=user.id,
        project_id=project.id,
        primary_genre_id=pg.id,
        primary_subcategory_id=ps.id,
        primary_register_id="formal",
        secondary_genre_id=sg.id,
        secondary_subcategory_id=ss.id,
        secondary_register_id="casual",
        storyteller_id=storyteller.id,
        description=None,
        segment_count=2,
    )

    await persist_split_segments(db_session, payload, _segment_results(2))

    for new_id in ("child-0", "child-1"):
        child = await db_session.get(OC_Recording, new_id)
        assert child is not None
        assert child.cleaning_status == CleaningStatus.NONE


@pytest.mark.asyncio
async def test_persist_split_segments_keeps_lineage_fields_intact(
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)
    pg, ps, sg, ss = await _seed_two_genres(db_session)
    storyteller = await _seed_storyteller(db_session, project.id)
    parent = await _seed_parent_with_full_metadata(
        db_session,
        user_id=user.id,
        project_id=project.id,
        primary_genre_id=pg.id,
        primary_subcategory_id=ps.id,
        primary_register_id="formal",
        secondary_genre_id=sg.id,
        secondary_subcategory_id=ss.id,
        secondary_register_id="casual",
        storyteller_id=storyteller.id,
    )
    payload = _payload_with_inheritance(
        recording_id=parent.id,
        user_id=user.id,
        project_id=project.id,
        primary_genre_id=pg.id,
        primary_subcategory_id=ps.id,
        primary_register_id="formal",
        secondary_genre_id=sg.id,
        secondary_subcategory_id=ss.id,
        secondary_register_id="casual",
        storyteller_id=storyteller.id,
        description="x",
        segment_count=3,
    )

    new_ids = await persist_split_segments(db_session, payload, _segment_results(3))

    for i, new_id in enumerate(new_ids):
        child = await db_session.get(OC_Recording, new_id)
        assert child is not None
        assert child.split_from_id == parent.id
        assert child.split_index == i
        assert child.split_segment_count == 3


@pytest.mark.asyncio
async def test_persist_split_segments_archives_parent_after_split(
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)
    pg, ps, sg, ss = await _seed_two_genres(db_session)
    storyteller = await _seed_storyteller(db_session, project.id)
    parent = await _seed_parent_with_full_metadata(
        db_session,
        user_id=user.id,
        project_id=project.id,
        primary_genre_id=pg.id,
        primary_subcategory_id=ps.id,
        primary_register_id="formal",
        secondary_genre_id=sg.id,
        secondary_subcategory_id=ss.id,
        secondary_register_id="casual",
        storyteller_id=storyteller.id,
    )
    payload = _payload_with_inheritance(
        recording_id=parent.id,
        user_id=user.id,
        project_id=project.id,
        primary_genre_id=pg.id,
        primary_subcategory_id=ps.id,
        primary_register_id="formal",
        secondary_genre_id=sg.id,
        secondary_subcategory_id=ss.id,
        secondary_register_id="casual",
        storyteller_id=storyteller.id,
        description=None,
        segment_count=2,
    )

    await persist_split_segments(db_session, payload, _segment_results(2))

    refreshed = await db_session.get(OC_Recording, parent.id)
    assert refreshed is not None
    assert refreshed.splitting_status == SplittingStatus.ARCHIVED_AFTER_SPLIT


@pytest.mark.asyncio
async def test_persist_split_segments_keeps_nulls_as_nulls_when_parent_has_no_metadata(
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)
    pg, ps, _, _ = await _seed_two_genres(db_session)
    parent = OC_Recording(
        project_id=project.id,
        genre_id=pg.id,
        subcategory_id=ps.id,
        user_id=user.id,
        title="bare parent",
        duration_seconds=60.0,
        file_size_bytes=10_000,
        format="m4a",
        gcs_url="https://example.com/p.m4a",
        upload_status=UploadStatus.VERIFIED,
        cleaning_status=CleaningStatus.NONE,
        splitting_status=SplittingStatus.SPLITTING,
        recorded_at=datetime.now(UTC),
    )
    db_session.add(parent)
    await db_session.commit()
    await db_session.refresh(parent)
    payload = _payload_with_inheritance(
        recording_id=parent.id,
        user_id=user.id,
        project_id=project.id,
        primary_genre_id=pg.id,
        primary_subcategory_id=ps.id,
        primary_register_id=None,
        secondary_genre_id=None,
        secondary_subcategory_id=None,
        secondary_register_id=None,
        storyteller_id=None,
        description=None,
        segment_count=1,
    )

    await persist_split_segments(db_session, payload, _segment_results(1))

    child = await db_session.get(OC_Recording, "child-0")
    assert child is not None
    assert child.description is None
    assert child.storyteller_id is None
    assert child.secondary_genre_id is None
    assert child.secondary_subcategory_id is None
    assert child.secondary_register_id is None


@pytest.mark.asyncio
async def test_request_split_snapshots_parent_metadata_into_payload(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = await make_user(db_session)
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)
    pg, ps, sg, ss = await _seed_two_genres(db_session)
    storyteller = await _seed_storyteller(db_session, project.id)
    parent = await _seed_parent_with_full_metadata(
        db_session,
        user_id=user.id,
        project_id=project.id,
        primary_genre_id=pg.id,
        primary_subcategory_id=ps.id,
        primary_register_id="formal",
        secondary_genre_id=sg.id,
        secondary_subcategory_id=ss.id,
        secondary_register_id="casual",
        storyteller_id=storyteller.id,
        description="An old story about the river",
    )

    captured: list[inngest.Event] = []

    async def fake_send(event: inngest.Event) -> list[str]:
        captured.append(event)
        return []

    monkeypatch.setattr(split_service.inngest_client, "send", fake_send)

    result = await request_split(
        db_session,
        parent.id,
        [
            SplitSegment(start_seconds=0.0, end_seconds=10.0),
            SplitSegment(start_seconds=10.0, end_seconds=20.0),
        ],
        user.id,
    )

    assert result.id == parent.id
    assert result.splitting_status == SplittingStatus.SPLITTING

    assert len(captured) == 1
    event = captured[0]
    assert event.name == OCRecordingEvent.SPLIT_REQUESTED
    assert event.data["recording_id"] == parent.id
    assert event.data["description"] == "An old story about the river"
    assert event.data["storyteller_id"] == storyteller.id
    assert event.data["secondary_genre_id"] == sg.id
    assert event.data["secondary_subcategory_id"] == ss.id
    assert event.data["secondary_register_id"] == "casual"


@pytest.mark.asyncio
async def test_request_split_rejects_segment_whose_effective_triple_matches_parent_secondary(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.exceptions import SegmentClassificationConflictError

    user = await make_user(db_session)
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)
    pg, ps, sg, ss = await _seed_two_genres(db_session)
    storyteller = await _seed_storyteller(db_session, project.id)
    parent = await _seed_parent_with_full_metadata(
        db_session,
        user_id=user.id,
        project_id=project.id,
        primary_genre_id=pg.id,
        primary_subcategory_id=ps.id,
        primary_register_id="formal",
        secondary_genre_id=sg.id,
        secondary_subcategory_id=ss.id,
        secondary_register_id="ceremonial",
        storyteller_id=storyteller.id,
    )

    captured: list[inngest.Event] = []

    async def fake_send(event: inngest.Event) -> list[str]:
        captured.append(event)
        return []

    monkeypatch.setattr(split_service.inngest_client, "send", fake_send)

    with pytest.raises(SegmentClassificationConflictError):
        await request_split(
            db_session,
            parent.id,
            [
                SplitSegment(
                    start_seconds=0.0,
                    end_seconds=10.0,
                    genre_id=sg.id,
                    subcategory_id=ss.id,
                    register_id="ceremonial",
                ),
            ],
            user.id,
        )

    assert captured == []


@pytest.mark.asyncio
async def test_request_split_allows_segment_with_single_field_overlap_with_parent_secondary(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = await make_user(db_session)
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)
    pg, ps, sg, ss = await _seed_two_genres(db_session)
    storyteller = await _seed_storyteller(db_session, project.id)
    parent = await _seed_parent_with_full_metadata(
        db_session,
        user_id=user.id,
        project_id=project.id,
        primary_genre_id=pg.id,
        primary_subcategory_id=ps.id,
        primary_register_id="formal",
        secondary_genre_id=sg.id,
        secondary_subcategory_id=ss.id,
        secondary_register_id="ceremonial",
        storyteller_id=storyteller.id,
    )

    captured: list[inngest.Event] = []

    async def fake_send(event: inngest.Event) -> list[str]:
        captured.append(event)
        return []

    monkeypatch.setattr(split_service.inngest_client, "send", fake_send)

    result = await request_split(
        db_session,
        parent.id,
        [
            SplitSegment(
                start_seconds=0.0,
                end_seconds=10.0,
                register_id="ceremonial",
            ),
        ],
        user.id,
    )

    assert result.id == parent.id
    assert len(captured) == 1


def test_split_requested_payload_round_trips_inherited_metadata_fields() -> None:
    payload = SplitRequestedPayload(
        recording_id="rec-1",
        user_id="u-1",
        segments=[
            SplitSegmentData(
                start_seconds=0.0,
                end_seconds=10.0,
                genre_id="g",
                subcategory_id="s",
            )
        ],
        project_id="p",
        format="m4a",
        title="x",
        recorded_at=datetime.now(UTC).isoformat(),
        description="hello",
        storyteller_id="st-1",
        secondary_genre_id="sg-1",
        secondary_subcategory_id="ss-1",
        secondary_register_id="sr-1",
    )

    dumped = payload.model_dump()
    rehydrated = SplitRequestedPayload.model_validate(dumped)

    assert rehydrated.description == "hello"
    assert rehydrated.storyteller_id == "st-1"
    assert rehydrated.secondary_genre_id == "sg-1"
    assert rehydrated.secondary_subcategory_id == "ss-1"
    assert rehydrated.secondary_register_id == "sr-1"
