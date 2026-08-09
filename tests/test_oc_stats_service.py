from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import SplittingStatus, UploadStatus
from app.db.models.oc_genre import OC_Genre, OC_Subcategory
from app.db.models.oc_recording import OC_Recording
from app.services.oral_collector import stats_service
from tests.baker import (
    make_language,
    make_oc_genre,
    make_oc_recording,
    make_oc_subcategory,
    make_project,
    make_user,
)

# `recording_service` and `app.inngest` import each other, so the package has to be fully up
# before the service can be reached, and it has to happen here at collection time — pulling
# it in from inside a test instead lands mid-fixture and corrupts the shared test engine.
pytest.importorskip("app.inngest")


def _import_recording_service():
    from app.services.oral_collector import recording_service

    return recording_service


async def _seed_two_genres(
    db: AsyncSession,
) -> tuple[OC_Genre, OC_Subcategory, OC_Genre, OC_Subcategory]:
    genre_a = await make_oc_genre(db, name="narrative", sort_order=0)
    genre_b = await make_oc_genre(db, name="wisdom", sort_order=1)
    sub_a = await make_oc_subcategory(db, genre_a.id, name="folktale", sort_order=0)
    sub_b = await make_oc_subcategory(db, genre_b.id, name="proverb", sort_order=0)
    return genre_a, sub_a, genre_b, sub_b


async def _seed_project(db: AsyncSession) -> str:
    lang = await make_language(db)
    project = await make_project(db, lang.id)
    return project.id


@pytest.mark.asyncio
async def test_genre_stats_counts_primary_only_ignores_secondary(
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre_a, sub_a, genre_b, sub_b = await _seed_two_genres(db_session)

    await make_oc_recording(
        db_session,
        project_id,
        genre_a.id,
        sub_a.id,
        secondary_genre_id=genre_b.id,
        secondary_subcategory_id=sub_b.id,
        secondary_register_id="consultative",
        user_id=user.id,
        title="ambiguous recording",
        duration_seconds=3600.0,
        upload_status=UploadStatus.UPLOADED,
    )

    response = await stats_service.get_genre_stats(db_session, project_id)

    genre_ids = {g.genre_id for g in response.genres}
    assert genre_a.id in genre_ids, "primary genre must appear in stats"
    assert genre_b.id not in genre_ids, (
        "secondary genre must NOT appear in stats — "
        "the counter would double-count ambiguous recordings otherwise"
    )

    stat_a = next(g for g in response.genres if g.genre_id == genre_a.id)
    assert stat_a.duration_seconds == 3600.0
    assert stat_a.recording_count == 1

    sub_ids = {s.subcategory_id for s in response.subcategories}
    assert sub_a.id in sub_ids
    assert sub_b.id not in sub_ids, "secondary subcategory must NOT appear in stats"


@pytest.mark.asyncio
async def test_genre_stats_aggregates_only_primary_across_multiple_recordings(
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre_a, sub_a, genre_b, sub_b = await _seed_two_genres(db_session)

    for _ in range(3):
        db_session.add(
            OC_Recording(
                project_id=project_id,
                genre_id=genre_a.id,
                subcategory_id=sub_a.id,
                secondary_genre_id=genre_b.id,
                secondary_subcategory_id=sub_b.id,
                user_id=user.id,
                duration_seconds=1800.0,
                file_size_bytes=1024,
                format="m4a",
                upload_status=UploadStatus.UPLOADED,
                recorded_at=datetime.now(UTC),
            )
        )
    await db_session.commit()

    response = await stats_service.get_genre_stats(db_session, project_id)

    stat_a = next(g for g in response.genres if g.genre_id == genre_a.id)
    assert stat_a.recording_count == 3
    assert stat_a.duration_seconds == 5400.0

    assert genre_b.id not in {g.genre_id for g in response.genres}


async def _seed_visible_and_archived(
    db: AsyncSession,
) -> tuple[str, OC_Genre, OC_Subcategory]:
    """A project holding one ordinary recording and one archived-after-split parent.

    Both are `VERIFIED`, so `ACTIVE_UPLOAD_STATUSES` keeps them; only `splitting_status`
    tells them apart.
    """
    user = await make_user(db)
    project_id = await _seed_project(db)
    genre = await make_oc_genre(db, name="narrative", sort_order=0)
    sub = await make_oc_subcategory(db, genre.id, name="folktale", sort_order=0)

    await make_oc_recording(
        db,
        project_id,
        genre.id,
        sub.id,
        user_id=user.id,
        title="visible recording",
        duration_seconds=120.0,
        upload_status=UploadStatus.VERIFIED,
    )
    await make_oc_recording(
        db,
        project_id,
        genre.id,
        sub.id,
        user_id=user.id,
        title="archived parent",
        duration_seconds=900.0,
        upload_status=UploadStatus.VERIFIED,
        splitting_status=SplittingStatus.ARCHIVED_AFTER_SPLIT,
    )
    return project_id, genre, sub


@pytest.mark.asyncio
async def test_genre_stats_excludes_archived_after_split(db_session: AsyncSession) -> None:
    project_id, genre, _sub = await _seed_visible_and_archived(db_session)

    response = await stats_service.get_genre_stats(db_session, project_id)

    stat = next(g for g in response.genres if g.genre_id == genre.id)
    assert stat.recording_count == 1, (
        "an archived-after-split parent is hidden from the listing, so counting it "
        "shows a total the user cannot open"
    )
    assert stat.duration_seconds == 120.0, "the archived parent's duration must not be summed"


@pytest.mark.asyncio
async def test_subcategory_stats_excludes_archived_after_split(db_session: AsyncSession) -> None:
    project_id, _genre, sub = await _seed_visible_and_archived(db_session)

    response = await stats_service.get_genre_stats(db_session, project_id)

    stat = next(s for s in response.subcategories if s.subcategory_id == sub.id)
    assert stat.recording_count == 1
    assert stat.duration_seconds == 120.0


@pytest.mark.asyncio
async def test_genre_stats_counts_the_same_set_the_listing_returns(
    db_session: AsyncSession,
) -> None:
    """The split leaves the parent archived beside its two segment rows.

    Counting the parent as well as its segments reports the same audio twice, which is the
    shape the home card was inflated by.
    """
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    genre = await make_oc_genre(db_session, name="narrative", sort_order=0)
    sub = await make_oc_subcategory(db_session, genre.id, name="folktale", sort_order=0)

    await make_oc_recording(
        db_session,
        project_id,
        genre.id,
        sub.id,
        user_id=user.id,
        title="parent (archived)",
        duration_seconds=900.0,
        upload_status=UploadStatus.VERIFIED,
        splitting_status=SplittingStatus.ARCHIVED_AFTER_SPLIT,
    )
    for index, seconds in enumerate((400.0, 500.0)):
        await make_oc_recording(
            db_session,
            project_id,
            genre.id,
            sub.id,
            user_id=user.id,
            title=f"parent (segment {index + 1})",
            duration_seconds=seconds,
            upload_status=UploadStatus.VERIFIED,
        )

    response = await stats_service.get_genre_stats(db_session, project_id)
    listed = await _import_recording_service().list_recordings(db_session, project_id)

    counted = sum(g.recording_count for g in response.genres)
    assert counted == len(listed), (
        "the stats and the listing describe one set; they must not disagree about "
        "archived-after-split recordings"
    )
    assert counted == 2

    counted_seconds = sum(g.duration_seconds for g in response.genres)
    assert counted_seconds == 900.0, "the segments' audio must be counted once, not twice"
