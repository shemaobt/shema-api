from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import UploadStatus
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
