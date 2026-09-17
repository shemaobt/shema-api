"""Counting and filtering by review flag (ENG-373 item 7).

The counts feed the project screen's "Revisão do acervo" block and the list's filter
chips. Both have to describe the same set of recordings the list itself shows, or the
number on the chip and the rows behind it disagree.
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ReviewFlagCode, SplittingStatus, UploadStatus
from app.services.oral_collector.review_flags import UNCLASSIFIED_GENRE_ID
from tests.baker import (
    make_language,
    make_oc_recording,
    make_oc_storyteller,
    make_oc_taxonomy_with_sentinel,
    make_project,
    make_user,
)

pytest.importorskip("app.inngest")

SUFFICIENT = "a description long enough to satisfy the rule"
INSUFFICIENT = "too short"

NOTHING_PENDING = dict.fromkeys(ReviewFlagCode, 0)
"""For tests whose subject is which recordings were counted, not which codes exist.

The two tests that pin the zero-filled shape itself spell the codes out, so that contract
still fails loudly when it changes.
"""


def _project_service():
    from app.services.oral_collector import project_service

    return project_service


def _recording_service():
    from app.services.oral_collector import recording_service

    return recording_service


# --- counts for the project screen -----------------------------------------------------


async def test_the_stats_count_each_flag_code_separately(db_session: AsyncSession) -> None:
    genre, sub = await make_oc_taxonomy_with_sentinel(db_session)
    user = await make_user(db_session)
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)
    storyteller = await make_oc_storyteller(db_session, project.id, created_by_user_id=user.id)

    await make_oc_recording(
        db_session,
        project.id,
        UNCLASSIFIED_GENRE_ID,
        UNCLASSIFIED_GENRE_ID,
        user_id=user.id,
        storyteller_id=storyteller.id,
        description=SUFFICIENT,
        title="no classification",
        recompute_flags=True,
    )
    await make_oc_recording(
        db_session,
        project.id,
        genre.id,
        sub.id,
        user_id=user.id,
        register_id="formal",
        storyteller_id=storyteller.id,
        description=INSUFFICIENT,
        title="weak description",
        recompute_flags=True,
    )
    await make_oc_recording(
        db_session,
        project.id,
        genre.id,
        sub.id,
        user_id=user.id,
        register_id="formal",
        description=SUFFICIENT,
        title="no storyteller",
        recompute_flags=True,
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
    await make_oc_taxonomy_with_sentinel(db_session)
    user = await make_user(db_session)
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)
    await make_oc_recording(
        db_session,
        project.id,
        UNCLASSIFIED_GENRE_ID,
        UNCLASSIFIED_GENRE_ID,
        user_id=user.id,
        description=INSUFFICIENT,
        title="recording",
        recompute_flags=True,
    )

    stats = await _project_service().get_project_stats(db_session, project.id)

    assert stats.review_flag_counts == {
        ReviewFlagCode.MISSING_CLASSIFICATION: 1,
        ReviewFlagCode.INSUFFICIENT_DESCRIPTION: 1,
        ReviewFlagCode.MISSING_STORYTELLER: 1,
    }
    assert stats.recordings_with_review_flags == 1


async def test_a_project_with_nothing_pending_reports_zeros(db_session: AsyncSession) -> None:
    genre, sub = await make_oc_taxonomy_with_sentinel(db_session)
    user = await make_user(db_session)
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)
    storyteller = await make_oc_storyteller(db_session, project.id, created_by_user_id=user.id)
    await make_oc_recording(
        db_session,
        project.id,
        genre.id,
        sub.id,
        user_id=user.id,
        register_id="formal",
        storyteller_id=storyteller.id,
        description=SUFFICIENT,
        title="recording",
        recompute_flags=True,
    )

    stats = await _project_service().get_project_stats(db_session, project.id)

    assert stats.review_flag_counts == {
        ReviewFlagCode.MISSING_CLASSIFICATION: 0,
        ReviewFlagCode.INSUFFICIENT_DESCRIPTION: 0,
        ReviewFlagCode.MISSING_STORYTELLER: 0,
    }
    assert stats.recordings_with_review_flags == 0


async def test_a_code_no_recording_carries_is_reported_as_zero(db_session: AsyncSession) -> None:
    genre, sub = await make_oc_taxonomy_with_sentinel(db_session)
    user = await make_user(db_session)
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)
    await make_oc_recording(
        db_session,
        project.id,
        genre.id,
        sub.id,
        user_id=user.id,
        register_id="formal",
        description=SUFFICIENT,
        title="no storyteller",
        recompute_flags=True,
    )

    stats = await _project_service().get_project_stats(db_session, project.id)

    assert stats.review_flag_counts == {
        ReviewFlagCode.MISSING_CLASSIFICATION: 0,
        ReviewFlagCode.INSUFFICIENT_DESCRIPTION: 0,
        ReviewFlagCode.MISSING_STORYTELLER: 1,
    }
    assert stats.recordings_with_review_flags == 1


async def test_the_counts_ignore_recordings_the_list_never_shows(db_session: AsyncSession) -> None:
    await make_oc_taxonomy_with_sentinel(db_session)
    user = await make_user(db_session)
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)
    await make_oc_recording(
        db_session,
        project.id,
        UNCLASSIFIED_GENRE_ID,
        UNCLASSIFIED_GENRE_ID,
        user_id=user.id,
        description=SUFFICIENT,
        title="archived after split",
        splitting_status=SplittingStatus.ARCHIVED_AFTER_SPLIT,
        recompute_flags=True,
    )
    await make_oc_recording(
        db_session,
        project.id,
        UNCLASSIFIED_GENRE_ID,
        UNCLASSIFIED_GENRE_ID,
        user_id=user.id,
        description=SUFFICIENT,
        title="still on the device",
        upload_status=UploadStatus.LOCAL,
        recompute_flags=True,
    )

    stats = await _project_service().get_project_stats(db_session, project.id)

    assert stats.review_flag_counts == NOTHING_PENDING
    assert stats.recordings_with_review_flags == 0


async def test_the_counts_stay_inside_the_project(db_session: AsyncSession) -> None:
    await make_oc_taxonomy_with_sentinel(db_session)
    user = await make_user(db_session)
    lang = await make_language(db_session)
    mine = await make_project(db_session, lang.id, name="mine")
    other = await make_project(db_session, lang.id, name="other")
    await make_oc_recording(
        db_session,
        other.id,
        UNCLASSIFIED_GENRE_ID,
        UNCLASSIFIED_GENRE_ID,
        user_id=user.id,
        description=SUFFICIENT,
        title="recording",
        recompute_flags=True,
    )

    stats = await _project_service().get_project_stats(db_session, mine.id)

    assert stats.review_flag_counts == NOTHING_PENDING


# --- the list filter -------------------------------------------------------------------


async def test_filtering_by_flag_returns_only_the_recordings_that_carry_it(
    db_session: AsyncSession,
) -> None:
    genre, sub = await make_oc_taxonomy_with_sentinel(db_session)
    user = await make_user(db_session)
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)
    wanted = await make_oc_recording(
        db_session,
        project.id,
        genre.id,
        sub.id,
        user_id=user.id,
        register_id="formal",
        description=SUFFICIENT,
        title="no storyteller",
        recompute_flags=True,
    )
    await make_oc_recording(
        db_session,
        project.id,
        UNCLASSIFIED_GENRE_ID,
        UNCLASSIFIED_GENRE_ID,
        user_id=user.id,
        register_id="formal",
        description=SUFFICIENT,
        title="unclassified but has a storyteller",
        storyteller_id=None,
        recompute_flags=True,
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
    genre, sub = await make_oc_taxonomy_with_sentinel(db_session)
    user = await make_user(db_session)
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)
    storyteller = await make_oc_storyteller(db_session, project.id, created_by_user_id=user.id)

    # Five without a storyteller, each preceded by one that has one, so a filter applied
    # after the page was cut would return two or three instead of five.
    for index in range(5):
        await make_oc_recording(
            db_session,
            project.id,
            genre.id,
            sub.id,
            user_id=user.id,
            register_id="formal",
            storyteller_id=storyteller.id,
            description=SUFFICIENT,
            title=f"complete {index}",
            recorded_at=datetime(2026, 1, 1, 12, index * 2, tzinfo=UTC),
            recompute_flags=True,
        )
        await make_oc_recording(
            db_session,
            project.id,
            genre.id,
            sub.id,
            user_id=user.id,
            register_id="formal",
            description=SUFFICIENT,
            title=f"pending {index}",
            recorded_at=datetime(2026, 1, 1, 12, index * 2 + 1, tzinfo=UTC),
            recompute_flags=True,
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
    genre, sub = await make_oc_taxonomy_with_sentinel(db_session)
    user = await make_user(db_session)
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)
    older = await make_oc_recording(
        db_session,
        project.id,
        genre.id,
        sub.id,
        user_id=user.id,
        register_id="formal",
        description=SUFFICIENT,
        title="older",
        recorded_at=datetime(2026, 1, 1, tzinfo=UTC),
        recompute_flags=True,
    )
    newer = await make_oc_recording(
        db_session,
        project.id,
        genre.id,
        sub.id,
        user_id=user.id,
        register_id="formal",
        description=SUFFICIENT,
        title="newer",
        recorded_at=datetime(2026, 6, 1, tzinfo=UTC),
        recompute_flags=True,
    )

    found = await _recording_service().list_recordings(
        db_session, project.id, review_flag=ReviewFlagCode.MISSING_STORYTELLER
    )

    assert [r.id for r in found] == [newer.id, older.id]


async def test_the_flag_filter_composes_with_the_other_filters(db_session: AsyncSession) -> None:
    genre, sub = await make_oc_taxonomy_with_sentinel(db_session)
    user = await make_user(db_session)
    other_user = await make_user(db_session, email="other@example.com")
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)
    mine = await make_oc_recording(
        db_session,
        project.id,
        genre.id,
        sub.id,
        user_id=user.id,
        register_id="formal",
        description=SUFFICIENT,
        title="mine",
        recompute_flags=True,
    )
    await make_oc_recording(
        db_session,
        project.id,
        genre.id,
        sub.id,
        user_id=other_user.id,
        register_id="formal",
        description=SUFFICIENT,
        title="theirs",
        recompute_flags=True,
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
    genre, sub = await make_oc_taxonomy_with_sentinel(db_session)
    user = await make_user(db_session)
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)
    await make_oc_recording(
        db_session,
        project.id,
        genre.id,
        sub.id,
        user_id=user.id,
        register_id="formal",
        description=SUFFICIENT,
        title="archived",
        splitting_status=SplittingStatus.ARCHIVED_AFTER_SPLIT,
        recompute_flags=True,
    )

    found = await _recording_service().list_recordings(
        db_session, project.id, review_flag=ReviewFlagCode.MISSING_STORYTELLER
    )

    assert found == []


# --- the published totals describe the same rows the list does -------------------------


async def test_the_totals_ignore_the_archived_parent_of_a_split(db_session: AsyncSession) -> None:
    genre, sub = await make_oc_taxonomy_with_sentinel(db_session)
    user = await make_user(db_session)
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)
    parent = await make_oc_recording(
        db_session,
        project.id,
        genre.id,
        sub.id,
        user_id=user.id,
        register_id="formal",
        description=SUFFICIENT,
        title="parent",
        splitting_status=SplittingStatus.ARCHIVED_AFTER_SPLIT,
        recompute_flags=True,
    )
    parent.duration_seconds = 30.0
    parent.file_size_bytes = 3072
    await db_session.commit()
    for index in range(3):
        await make_oc_recording(
            db_session,
            project.id,
            genre.id,
            sub.id,
            user_id=user.id,
            register_id="formal",
            description=SUFFICIENT,
            title=f"segment {index}",
            recompute_flags=True,
        )

    stats = await _project_service().get_project_stats(db_session, project.id)
    listed = await _recording_service().list_recordings(db_session, project.id)

    assert stats.total_recordings == len(listed) == 3
    assert stats.total_duration_seconds == 30.0
    assert stats.total_file_size_bytes == 3072


async def test_the_batch_totals_ignore_the_archived_parent_of_a_split(
    db_session: AsyncSession,
) -> None:
    genre, sub = await make_oc_taxonomy_with_sentinel(db_session)
    user = await make_user(db_session)
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)
    await make_oc_recording(
        db_session,
        project.id,
        genre.id,
        sub.id,
        user_id=user.id,
        register_id="formal",
        description=SUFFICIENT,
        title="parent",
        splitting_status=SplittingStatus.ARCHIVED_AFTER_SPLIT,
        recompute_flags=True,
    )
    await make_oc_recording(
        db_session,
        project.id,
        genre.id,
        sub.id,
        user_id=user.id,
        register_id="formal",
        description=SUFFICIENT,
        title="segment",
        recompute_flags=True,
    )

    batch = await _project_service().get_projects_batch_stats(db_session, [project.id])

    assert batch[project.id]["recordings"] == 1
    assert batch[project.id]["duration"] == 10.0
