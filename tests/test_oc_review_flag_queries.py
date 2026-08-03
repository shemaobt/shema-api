"""Counting and filtering by review flag (ENG-373 item 7).

The counts feed the project screen's "Revisão do acervo" block and the list's filter
chips. Both have to describe the same set of recordings the list itself shows, or the
number on the chip and the rows behind it disagree.
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ReviewFlagCode, SplittingStatus, UploadStatus
from app.db.models.oc_genre import OC_Genre, OC_Subcategory
from app.db.models.oc_recording import OC_Recording
from app.db.models.oc_storyteller import OC_Storyteller
from app.services.oral_collector.review_flags import recompute_review_flags
from tests.baker import make_language, make_project, make_user

pytest.importorskip("app.inngest")

UNCLASSIFIED = "unclassified"
SUFFICIENT = "a description long enough to satisfy the rule"
INSUFFICIENT = "too short"


def _project_service():
    from app.services.oral_collector import project_service

    return project_service


def _recording_service():
    from app.services.oral_collector import recording_service

    return recording_service


async def _seed_taxonomy(db: AsyncSession) -> tuple[OC_Genre, OC_Subcategory]:
    sentinel_genre = OC_Genre(id=UNCLASSIFIED, name="Unclassified", sort_order=9999)
    genre = OC_Genre(name="narrative", sort_order=0)
    db.add_all([sentinel_genre, genre])
    await db.flush()

    sentinel_sub = OC_Subcategory(
        id=UNCLASSIFIED, genre_id=UNCLASSIFIED, name="Unclassified", sort_order=9999
    )
    sub = OC_Subcategory(genre_id=genre.id, name="folktale", sort_order=0)
    db.add_all([sentinel_sub, sub])
    await db.commit()
    await db.refresh(genre)
    await db.refresh(sub)
    return genre, sub


async def _seed_recording(
    db: AsyncSession,
    *,
    project_id: str,
    genre_id: str,
    subcategory_id: str,
    user_id: str,
    register_id: str | None = None,
    storyteller_id: str | None = None,
    description: str | None = None,
    title: str = "recording",
    upload_status: str = UploadStatus.VERIFIED,
    splitting_status: str = SplittingStatus.NONE,
    recorded_at: datetime | None = None,
) -> OC_Recording:
    recording = OC_Recording(
        project_id=project_id,
        genre_id=genre_id,
        subcategory_id=subcategory_id,
        register_id=register_id,
        storyteller_id=storyteller_id,
        user_id=user_id,
        title=title,
        description=description,
        duration_seconds=10.0,
        file_size_bytes=1024,
        format="m4a",
        upload_status=upload_status,
        splitting_status=splitting_status,
        recorded_at=recorded_at or datetime.now(UTC),
    )
    recompute_review_flags(recording)
    db.add(recording)
    await db.commit()
    await db.refresh(recording)
    return recording


# --- counts for the project screen -----------------------------------------------------


async def test_the_stats_count_each_flag_code_separately(db_session: AsyncSession) -> None:
    genre, sub = await _seed_taxonomy(db_session)
    user = await make_user(db_session)
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)
    storyteller = OC_Storyteller(
        project_id=project.id, name="Ana", sex="female", created_by_user_id=user.id
    )
    db_session.add(storyteller)
    await db_session.commit()

    await _seed_recording(
        db_session,
        project_id=project.id,
        genre_id=UNCLASSIFIED,
        subcategory_id=UNCLASSIFIED,
        user_id=user.id,
        storyteller_id=storyteller.id,
        description=SUFFICIENT,
        title="no classification",
    )
    await _seed_recording(
        db_session,
        project_id=project.id,
        genre_id=genre.id,
        subcategory_id=sub.id,
        user_id=user.id,
        register_id="formal",
        storyteller_id=storyteller.id,
        description=INSUFFICIENT,
        title="weak description",
    )
    await _seed_recording(
        db_session,
        project_id=project.id,
        genre_id=genre.id,
        subcategory_id=sub.id,
        user_id=user.id,
        register_id="formal",
        description=SUFFICIENT,
        title="no storyteller",
    )

    stats = await _project_service().get_project_stats(db_session, project.id)

    assert stats.review_flag_counts == {
        ReviewFlagCode.MISSING_CLASSIFICATION: 1,
        ReviewFlagCode.INSUFFICIENT_DESCRIPTION: 1,
        ReviewFlagCode.MISSING_STORYTELLER: 1,
    }


async def test_a_recording_with_three_flags_is_one_recording_but_three_counts(
    db_session: AsyncSession,
) -> None:
    await _seed_taxonomy(db_session)
    user = await make_user(db_session)
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)
    await _seed_recording(
        db_session,
        project_id=project.id,
        genre_id=UNCLASSIFIED,
        subcategory_id=UNCLASSIFIED,
        user_id=user.id,
        description=INSUFFICIENT,
    )

    stats = await _project_service().get_project_stats(db_session, project.id)

    assert stats.review_flag_counts == {
        ReviewFlagCode.MISSING_CLASSIFICATION: 1,
        ReviewFlagCode.INSUFFICIENT_DESCRIPTION: 1,
        ReviewFlagCode.MISSING_STORYTELLER: 1,
    }
    assert stats.recordings_with_review_flags == 1


async def test_a_project_with_nothing_pending_reports_zeros(db_session: AsyncSession) -> None:
    genre, sub = await _seed_taxonomy(db_session)
    user = await make_user(db_session)
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)
    storyteller = OC_Storyteller(
        project_id=project.id, name="Ana", sex="female", created_by_user_id=user.id
    )
    db_session.add(storyteller)
    await db_session.commit()
    await _seed_recording(
        db_session,
        project_id=project.id,
        genre_id=genre.id,
        subcategory_id=sub.id,
        user_id=user.id,
        register_id="formal",
        storyteller_id=storyteller.id,
        description=SUFFICIENT,
    )

    stats = await _project_service().get_project_stats(db_session, project.id)

    assert stats.review_flag_counts == {}
    assert stats.recordings_with_review_flags == 0


async def test_the_counts_ignore_recordings_the_list_never_shows(db_session: AsyncSession) -> None:
    await _seed_taxonomy(db_session)
    user = await make_user(db_session)
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)
    await _seed_recording(
        db_session,
        project_id=project.id,
        genre_id=UNCLASSIFIED,
        subcategory_id=UNCLASSIFIED,
        user_id=user.id,
        description=SUFFICIENT,
        title="archived after split",
        splitting_status=SplittingStatus.ARCHIVED_AFTER_SPLIT,
    )
    await _seed_recording(
        db_session,
        project_id=project.id,
        genre_id=UNCLASSIFIED,
        subcategory_id=UNCLASSIFIED,
        user_id=user.id,
        description=SUFFICIENT,
        title="still on the device",
        upload_status=UploadStatus.LOCAL,
    )

    stats = await _project_service().get_project_stats(db_session, project.id)

    assert stats.review_flag_counts == {}
    assert stats.recordings_with_review_flags == 0


async def test_the_counts_stay_inside_the_project(db_session: AsyncSession) -> None:
    await _seed_taxonomy(db_session)
    user = await make_user(db_session)
    lang = await make_language(db_session)
    mine = await make_project(db_session, lang.id, name="mine")
    other = await make_project(db_session, lang.id, name="other")
    await _seed_recording(
        db_session,
        project_id=other.id,
        genre_id=UNCLASSIFIED,
        subcategory_id=UNCLASSIFIED,
        user_id=user.id,
        description=SUFFICIENT,
    )

    stats = await _project_service().get_project_stats(db_session, mine.id)

    assert stats.review_flag_counts == {}


# --- the list filter -------------------------------------------------------------------


async def test_filtering_by_flag_returns_only_the_recordings_that_carry_it(
    db_session: AsyncSession,
) -> None:
    genre, sub = await _seed_taxonomy(db_session)
    user = await make_user(db_session)
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)
    wanted = await _seed_recording(
        db_session,
        project_id=project.id,
        genre_id=genre.id,
        subcategory_id=sub.id,
        user_id=user.id,
        register_id="formal",
        description=SUFFICIENT,
        title="no storyteller",
    )
    await _seed_recording(
        db_session,
        project_id=project.id,
        genre_id=UNCLASSIFIED,
        subcategory_id=UNCLASSIFIED,
        user_id=user.id,
        register_id="formal",
        description=SUFFICIENT,
        title="unclassified but has a storyteller",
        storyteller_id=None,
    )

    found = await _recording_service().list_recordings(
        db_session, project.id, review_flag=ReviewFlagCode.INSUFFICIENT_DESCRIPTION
    )

    assert [r.id for r in found] == []

    found = await _recording_service().list_recordings(
        db_session, project.id, review_flag=ReviewFlagCode.MISSING_STORYTELLER
    )

    assert wanted.id in [r.id for r in found]


async def test_the_flag_filter_paginates_over_the_matches_not_the_page(
    db_session: AsyncSession,
) -> None:
    genre, sub = await _seed_taxonomy(db_session)
    user = await make_user(db_session)
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)
    storyteller = OC_Storyteller(
        project_id=project.id, name="Ana", sex="female", created_by_user_id=user.id
    )
    db_session.add(storyteller)
    await db_session.commit()

    # Five without a storyteller, each preceded by one that has one, so a filter applied
    # after the page was cut would return two or three instead of five.
    for index in range(5):
        await _seed_recording(
            db_session,
            project_id=project.id,
            genre_id=genre.id,
            subcategory_id=sub.id,
            user_id=user.id,
            register_id="formal",
            storyteller_id=storyteller.id,
            description=SUFFICIENT,
            title=f"complete {index}",
            recorded_at=datetime(2026, 1, 1, 12, index * 2, tzinfo=UTC),
        )
        await _seed_recording(
            db_session,
            project_id=project.id,
            genre_id=genre.id,
            subcategory_id=sub.id,
            user_id=user.id,
            register_id="formal",
            description=SUFFICIENT,
            title=f"pending {index}",
            recorded_at=datetime(2026, 1, 1, 12, index * 2 + 1, tzinfo=UTC),
        )

    first = await _recording_service().list_recordings(
        db_session,
        project.id,
        review_flag=ReviewFlagCode.MISSING_STORYTELLER,
        offset=0,
        limit=2,
    )
    second = await _recording_service().list_recordings(
        db_session,
        project.id,
        review_flag=ReviewFlagCode.MISSING_STORYTELLER,
        offset=2,
        limit=2,
    )
    third = await _recording_service().list_recordings(
        db_session,
        project.id,
        review_flag=ReviewFlagCode.MISSING_STORYTELLER,
        offset=4,
        limit=2,
    )

    assert len(first) == 2
    assert len(second) == 2
    assert len(third) == 1
    assert len({r.id for r in first + second + third}) == 5


async def test_the_flag_filter_keeps_the_list_ordering(db_session: AsyncSession) -> None:
    genre, sub = await _seed_taxonomy(db_session)
    user = await make_user(db_session)
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)
    older = await _seed_recording(
        db_session,
        project_id=project.id,
        genre_id=genre.id,
        subcategory_id=sub.id,
        user_id=user.id,
        register_id="formal",
        description=SUFFICIENT,
        title="older",
        recorded_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    newer = await _seed_recording(
        db_session,
        project_id=project.id,
        genre_id=genre.id,
        subcategory_id=sub.id,
        user_id=user.id,
        register_id="formal",
        description=SUFFICIENT,
        title="newer",
        recorded_at=datetime(2026, 6, 1, tzinfo=UTC),
    )

    found = await _recording_service().list_recordings(
        db_session, project.id, review_flag=ReviewFlagCode.MISSING_STORYTELLER
    )

    assert [r.id for r in found] == [newer.id, older.id]


async def test_the_flag_filter_composes_with_the_other_filters(db_session: AsyncSession) -> None:
    genre, sub = await _seed_taxonomy(db_session)
    user = await make_user(db_session)
    other_user = await make_user(db_session, email="other@example.com")
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)
    mine = await _seed_recording(
        db_session,
        project_id=project.id,
        genre_id=genre.id,
        subcategory_id=sub.id,
        user_id=user.id,
        register_id="formal",
        description=SUFFICIENT,
        title="mine",
    )
    await _seed_recording(
        db_session,
        project_id=project.id,
        genre_id=genre.id,
        subcategory_id=sub.id,
        user_id=other_user.id,
        register_id="formal",
        description=SUFFICIENT,
        title="theirs",
    )

    found = await _recording_service().list_recordings(
        db_session,
        project.id,
        review_flag=ReviewFlagCode.MISSING_STORYTELLER,
        user_id=user.id,
    )

    assert [r.id for r in found] == [mine.id]


async def test_an_archived_recording_never_reaches_the_flag_filter(
    db_session: AsyncSession,
) -> None:
    genre, sub = await _seed_taxonomy(db_session)
    user = await make_user(db_session)
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)
    await _seed_recording(
        db_session,
        project_id=project.id,
        genre_id=genre.id,
        subcategory_id=sub.id,
        user_id=user.id,
        register_id="formal",
        description=SUFFICIENT,
        title="archived",
        splitting_status=SplittingStatus.ARCHIVED_AFTER_SPLIT,
    )

    found = await _recording_service().list_recordings(
        db_session, project.id, review_flag=ReviewFlagCode.MISSING_STORYTELLER
    )

    assert found == []
